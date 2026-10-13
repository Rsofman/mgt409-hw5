"""FastAPI backend for the Campus Customs desk dashboard.

Start it from the backend/ folder:

    uvicorn main:app --reload --port 8000

Every shop fact and every change goes through the campus-customs MCP server.
Agents only prepare payments (pending approval requests); the approve route is
the only path that moves cash, and it runs only when a human clicks approve.
"""

import asyncio
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# `uvicorn main:app` imports this file as a top-level module, so make the
# project folder importable for the `backend` package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.approvals import audit_human, decide_async  # noqa: E402
from backend.audit import append_audit, read_audit  # noqa: E402
from backend.config import MODEL_NAME  # noqa: E402
from backend.mcp_tools import shop_mcp  # noqa: E402
from backend.reset_db import reset_db  # noqa: E402
from backend.team import run_ticket  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Keep one MCP connection open for the life of the server (startup takes ~10 s).
    async with shop_mcp:
        yield


app = FastAPI(
    title="Campus Customs Desk API",
    description="Backend for the agent-team dashboard. Mock shop: nothing contacts anyone.",
    lifespan=lifespan,
)
# The Vite dashboard (npm run dev) serves from http://localhost:5173.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent runs started from the dashboard. One run at a time, so the shared
# budget, the board, and the cash checks never interleave.
RUNS: dict[str, dict[str, Any]] = {}
_tasks: set[asyncio.Task] = set()
_active_run: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def mcp(name: str, args: dict | None = None) -> dict:
    return await shop_mcp.direct_call_tool(name, args or {})


def _require_idle(action: str) -> None:
    if _active_run is not None:
        run = RUNS[_active_run]
        raise HTTPException(
            409,
            f"Can't {action} while the team is working ticket {run['ticket_id']} "
            f"(run {_active_run}). Try again when it finishes.",
        )


# ---------------------------------------------------------------- tickets


@app.get("/tickets")
async def list_tickets():
    """All tickets with their board status, and whether each is open or resolved.

    `state` is "resolved" once the team has finished a run and the boss has made
    the final call; `status` is that call (resolved, awaiting_approval, blocked,
    needs_human). A ticket nobody has worked yet is "open".
    """
    board = await mcp("list_tickets")
    running = RUNS[_active_run]["ticket_id"] if _active_run else None
    return {
        "date_today": board["date_today"],
        "tickets": [
            {
                **t,
                "state": "open" if t["status"] == "open" else "resolved",
                "running": t["id"] == running,
            }
            for t in board["tickets"]
        ],
    }


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: int):
    """One ticket with everything on its board: drafts and payment approvals."""
    board = await mcp("list_board", {"ticket_id": ticket_id})
    if not board.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    return board


@app.get("/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int):
    """What each agent did on the ticket's latest run, built from the audit trail."""
    try:
        entries = read_audit()
    except ValueError:
        raise HTTPException(503, "Audit trail is being written; try again.")
    starts = [e for e in entries if e.get("ticket_id") == ticket_id
              and e.get("kind") == "run_start" and e.get("name") == "ticket"]
    if not starts:
        return {"ticket_id": ticket_id, "run_id": None, "agents": [], "decision": None}
    run_id = starts[-1]["run_id"]
    run = [e for e in entries if e.get("run_id") == run_id]

    agents: dict[str, dict[str, Any]] = {}
    for e in run:
        name = e.get("agent")
        if name in (None, "system"):
            continue
        a = agents.setdefault(name, {"agent": name, "summaries": [], "tools": {},
                                     "delegated_to": [], "tasks": []})
        kind, data = e.get("kind"), e.get("data") or {}
        if kind == "agent_start" and name != "boss":
            a["tasks"].append(data.get("task"))
        elif kind == "agent_output":
            out = data.get("output") or {}
            if out.get("summary"):
                a["summaries"].append(out["summary"])
        elif kind == "tool_call":
            a["tools"][e["name"]] = a["tools"].get(e["name"], 0) + 1
        elif kind == "delegation":
            a["delegated_to"].append(e["name"])

    decision = next((e["data"] for e in reversed(run) if e.get("kind") == "status"), None)
    end = next((e for e in reversed(run) if e.get("kind") == "run_end"), None)
    return {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "started_at": run[0].get("ts"),
        "finished_at": end.get("ts") if end else None,
        "budget": (end or run[-1]).get("budget"),
        "agents": list(agents.values()),
        "decision": decision,
    }


@app.get("/tickets/{ticket_id}/discount-options")
async def discount_options(ticket_id: int, pcts: list[float] | None = Query(None)):
    """Discount levels for a ticket's SKU and qty, with revenue, discount given, cost, and profit."""
    args: dict[str, Any] = {"ticket_id": ticket_id}
    if pcts:
        args["discount_pcts"] = pcts
    result = await mcp("discount_options", args)
    if not result.get("found"):
        raise HTTPException(404, result.get("error", "No pricing for this ticket."))
    return result


class TicketDecision(BaseModel):
    decided_by: str = Field(min_length=1, description="Name of the person deciding.")
    decision: Literal["offer_discount", "decline_discount", "wait_for_customer"]
    discount_pct: float | None = None
    note: str = ""


@app.post("/tickets/{ticket_id}/decision")
async def record_decision(ticket_id: int, body: TicketDecision):
    """A human records a decision on a ticket the boss sent to a human (e.g. which discount).

    No money moves. Re-run the ticket afterwards so the team acts on it.
    """
    _require_idle("record a decision")
    result = await mcp("record_human_decision", {"ticket_id": ticket_id, **body.model_dump()})
    kind = "human_ticket_decision" if result.get("recorded") else "human_ticket_decision_refused"
    audit_human(body.decided_by, kind, "record_human_decision", ticket_id,
                {"args": body.model_dump(), "result": result})
    if not result.get("recorded"):
        raise HTTPException(400, result.get("error", "Decision was not recorded."))
    return result


@app.post("/tickets/{ticket_id}/run", status_code=202)
async def run_team(ticket_id: int, wait: bool = False):
    """Start the agent team on a ticket. Returns a run id; poll /runs/{id} and /events."""
    global _active_run
    found = await mcp("get_ticket", {"ticket_id": ticket_id})
    if not found.get("found"):
        raise HTTPException(404, f"No ticket {ticket_id}.")
    _require_idle("start another run")

    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {
        "run_id": run_id,
        "ticket_id": ticket_id,
        "status": "running",
        "started_at": _now(),
        "finished_at": None,
        "decision": None,
        "error": None,
    }
    _active_run = run_id

    async def work() -> None:
        global _active_run
        try:
            result = await run_ticket(ticket_id, run_id=run_id)
            RUNS[run_id].update(
                status="finished",
                decision=result.decision.model_dump(mode="json"),
                tool_calls_used=result.tool_calls_used,
                delegations_used=result.delegations_used,
            )
        except Exception as exc:  # recorded for the dashboard; also in the audit trail
            RUNS[run_id].update(status="failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            RUNS[run_id]["finished_at"] = _now()
            _active_run = None

    task = asyncio.create_task(work())
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    if wait:
        await task
    return RUNS[run_id]


@app.get("/runs")
async def list_runs():
    """Agent runs started since the server came up, newest first."""
    return {"active_run": _active_run, "runs": list(reversed(RUNS.values()))}


@app.get("/runs/{run_id}")
async def get_run(run_id: str):
    """One run's status (running / finished / failed) and the boss's decision when done."""
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} since the server started.")
    return RUNS[run_id]


# ---------------------------------------------------------------- events


def _summarize(entry: dict[str, Any]) -> tuple[str | None, list[str], Any]:
    """(what the agent said, tools it used, the arguments) for one audit entry."""
    kind, name, data = entry.get("kind"), entry.get("name"), entry.get("data") or {}
    if not isinstance(data, dict):
        return (str(data), [], None)
    if kind == "model_response":
        calls = data.get("tool_calls") or []
        return (data.get("text"), [c["tool"] for c in calls],
                [{c["tool"]: c["args"]} for c in calls] or None)
    if kind == "tool_call":
        return (None, [name], data)
    if kind == "tool_result":
        return (None, [name], None)
    if kind == "agent_start":
        return (data.get("task"), [], None)
    if kind == "delegation":
        return (f"Delegated to {name}: {data.get('task')}", ["delegate"], None)
    if kind == "report":
        return (data.get("summary"), [], None)
    if kind == "agent_output":
        out = data.get("output") or {}
        return (out.get("summary"), [], None)
    if kind == "status":
        return (f"Status set to {name}: {data.get('summary')}", ["set_ticket_status"], None)
    if kind in ("human_decision", "payment", "human_ticket_decision"):
        return (f"{entry.get('agent')}: {name}", [name], data.get("args"))
    if kind in ("limit", "error"):
        return (f"{kind}: {name} {data}", [], None)
    return (None, [], None)


@app.get("/events")
async def recent_events(
    limit: int = Query(50, ge=1, le=500),
    ticket_id: int | None = None,
    run_id: str | None = None,
    after: int | None = Query(None, description="Only events with cursor greater than this."),
    include_model_requests: bool = False,
    raw: bool = False,
):
    """Recent agent events from output/audit_trail.json: who said what and which tools they used.

    Poll with ?after=<next_after> to get only new events.
    """
    try:
        entries = read_audit()
    except ValueError:
        # Another process (the approvals CLI) was mid-append; the next poll will see it.
        raise HTTPException(503, "Audit trail is being written; try again.")

    events = []
    for cursor, e in enumerate(entries):
        if after is not None and cursor <= after:
            continue
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if run_id is not None and e.get("run_id") != run_id:
            continue
        if e.get("kind") == "model_request" and not include_model_requests:
            continue
        said, tools, args = _summarize(e)
        event = {
            "cursor": cursor,
            "ts": e.get("ts"),
            "run_id": e.get("run_id"),
            "ticket_id": e.get("ticket_id"),
            "agent": e.get("agent"),
            "depth": e.get("depth"),
            "kind": e.get("kind"),
            "name": e.get("name"),
            "said": said,
            "tools": tools,
            "args": args,
        }
        if raw:
            event["data"] = e.get("data")
        events.append(event)

    events = events[-limit:]
    return {
        "events": events,
        "next_after": events[-1]["cursor"] if events else after,
        "total_in_trail": len(entries),
    }


# ---------------------------------------------------------------- approvals and cash


class HumanDecision(BaseModel):
    approver: str = Field(min_length=1, description="Name of the person clicking the button.")


@app.get("/approvals")
async def list_approvals(status: str | None = "pending", ticket_id: int | None = None):
    """Payment and purchase-order requests the agents prepared (default: pending ones)."""
    args: dict[str, Any] = {}
    if status:
        args["status"] = status
    if ticket_id is not None:
        args["ticket_id"] = ticket_id
    return await mcp("list_approvals", args)


@app.post("/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: HumanDecision):
    """A human approves a pending payment or purchase order; it is then paid and the books updated.

    This is the only route that can change cash. If cash no longer covers it,
    the payment is refused and nothing moves.
    """
    _require_idle("approve a payment")
    found = await mcp("get_approval", {"approval_id": approval_id})
    if not found.get("found"):
        raise HTTPException(404, f"No approval {approval_id}.")
    if found["approval"]["status"] != "pending":
        raise HTTPException(409, f"Approval {approval_id} is already '{found['approval']['status']}'.")

    decision = await decide_async(approval_id, body.approver, approve=True)
    if not decision.get("decided"):
        raise HTTPException(400, decision.get("error", "Approval was not recorded."))

    payment = await mcp("pay_approved", {"approval_id": approval_id,
                                          "paid_by": f"human:{body.approver}"})
    audit_human(body.approver, "payment", "pay_approved", found["approval"]["ticket_id"],
                {"args": {"approval_id": approval_id}, "result": payment})
    cash = await get_cash()
    if not payment.get("paid"):
        raise HTTPException(409, {"error": payment.get("error"), "payment": payment, "cash": cash})
    return {"approval": decision["approval"] | {"status": "paid"}, "payment": payment, "cash": cash}


@app.post("/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: HumanDecision):
    """A human rejects a pending request. No money moves."""
    decision = await decide_async(approval_id, body.approver, approve=False)
    if not decision.get("decided"):
        raise HTTPException(400, decision.get("error", "Rejection was not recorded."))
    return decision


@app.get("/cash")
async def get_cash():
    """Current checking balance from cash_accounts, plus what is owed against it."""
    cash = await mcp("check_cash")
    checking = next((a for a in cash["cash_accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {
        "account": "checking",
        "balance": checking["balance"],
        "as_of": checking["as_of"],
        "date_today": cash["date_today"],
        "total_obligations": cash["total_obligations"],
        "can_cover_all": cash["can_cover_all"],
        "shortfall": cash["shortfall"],
    }


# ---------------------------------------------------------------- reset and info


@app.post("/reset")
async def reset():
    """Reset data/campus_customs_new.db to the original values for a fresh run.

    The audit trail is never wiped; the reset itself is appended to it.
    """
    _require_idle("reset the database")
    reset_db()
    append_audit({"ts": _now(), "agent": "human", "kind": "reset", "name": "reset_db",
                  "ticket_id": None, "data": {"from": "data/campus_customs.db",
                                              "to": "data/campus_customs_new.db"}})
    return {"reset": True, **(await list_tickets()), "cash": await get_cash()}


@app.get("/")
async def index():
    """Health check and route list."""
    return {
        "service": "Campus Customs Desk API",
        "model": MODEL_NAME,
        "active_run": _active_run,
        "routes": sorted(
            f"{','.join(sorted(r.methods - {'HEAD'}))} {r.path}"
            for r in app.routes
            if getattr(r, "methods", None) and r.path not in ("/openapi.json",)
            and not r.path.startswith("/docs") and not r.path.startswith("/redoc")
        ),
    }

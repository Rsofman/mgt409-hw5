"""Runs the agent team on tickets.

    python -m backend.team run 101          # one ticket
    python -m backend.team run-all          # every open ticket (reset the DB first)
    python -m backend.team pay 3            # after a human approves approval 3

The boss always starts a ticket. Specialists are reached through `delegate`,
so the agent loop is: boss -> (any agent -> any agent)* -> boss decision.
Every step is appended to output/audit_trail.json. All shop data goes through
the campus-customs MCP server; nothing here reads the database directly.
"""

import argparse
import asyncio
import json
from collections.abc import Callable

from pydantic_ai import UnexpectedModelBehavior, UsageLimitExceeded

from .agents import get_agent
from .agents.base import run_agent
from .mcp_tools import shop_mcp
from .models import (
    AgentDeps,
    BossDecision,
    Finding,
    Priority,
    SpecialistReport,
    TeamEvent,
    TicketRunResult,
    TicketState,
    TicketStatus,
    TicketType,
)


async def _system_call(state: TicketState, name: str, args: dict) -> dict:
    """An MCP call made by the orchestrator itself (not an agent), logged to the trail."""
    state.log("system", "tool_call", name, args)
    result = await shop_mcp.direct_call_tool(name, args)
    state.log("system", "tool_result", name, result)
    return result


def _escalation(state: TicketState, ticket_type: str, reason: str) -> BossDecision:
    """Fallback decision when the team runs out of budget or the model misbehaves."""
    try:
        classification = TicketType(ticket_type)
    except ValueError:
        classification = TicketType.OTHER
    return BossDecision(
        ticket_id=state.ticket_id,
        classification=classification,
        priority=Priority.HIGH,
        status=TicketStatus.NEEDS_HUMAN,
        summary="The team could not finish this ticket within its limits.",
        findings=[
            Finding(fact=f"Ticket {state.ticket_id} was read from the board.",
                    source_tool="get_ticket", source_ids=[f"ticket {state.ticket_id}"])
        ],
        escalation_reason=reason,
    )


async def run_ticket(
    ticket_id: int,
    *,
    on_event: Callable[[TeamEvent], None] | None = None,
    run_id: str | None = None,
) -> TicketRunResult:
    state = TicketState(ticket_id=ticket_id, on_event=on_event)
    if run_id is not None:
        state.run_id = run_id
    async with shop_mcp:
        ticket = await _system_call(state, "get_ticket", {"ticket_id": ticket_id})
        if not ticket.get("found"):
            raise ValueError(f"No ticket {ticket_id} on the board.")
        state.date_today = ticket["date_today"]
        state.log("system", "run_start", "ticket", {"ticket": ticket["ticket"]})

        prompt = (
            f"New ticket {ticket_id} on the board. Shop date (desk.date_today) is "
            f"{state.date_today}.\n{json.dumps(ticket['ticket'], indent=2)}"
        )
        try:
            decision: BossDecision = await run_agent(
                get_agent("boss"), "boss", prompt, AgentDeps(agent="boss", state=state)
            )
        except (UsageLimitExceeded, UnexpectedModelBehavior) as exc:
            state.log("system", "error", type(exc).__name__, str(exc))
            decision = _escalation(state, ticket["ticket"]["type"], f"{type(exc).__name__}: {exc}")
        except Exception as exc:
            # Leave a trace in the audit trail before the crash propagates.
            state.log("system", "error", type(exc).__name__, repr(exc))
            raise

        await _system_call(
            state,
            "set_ticket_status",
            {
                "ticket_id": ticket_id,
                "status": decision.status.value,
                "summary": decision.summary,
                "set_by": "boss",
            },
        )
        state.log("boss", "status", decision.status.value, decision.model_dump(mode="json"))
        state.log("system", "run_end", "ticket", {
            "status": decision.status.value,
            "tool_calls_used": state.tool_calls,
            "delegations_used": state.delegations,
        })

    return TicketRunResult(
        run_id=state.run_id,
        ticket_id=ticket_id,
        decision=decision,
        tool_calls_used=state.tool_calls,
        delegations_used=state.delegations,
        events=state.events,
    )


async def run_open_tickets(
    *, on_event: Callable[[TeamEvent], None] | None = None
) -> list[TicketRunResult]:
    """Work every ticket that is still open, one at a time, in ticket order."""
    async with shop_mcp:
        board = await shop_mcp.direct_call_tool("list_open_tickets", {})
        ids = [t["id"] for t in board["tickets"] if t["status"] == "open"]
        return [await run_ticket(tid, on_event=on_event) for tid in ids]


async def pay_after_approval(
    approval_id: int, *, on_event: Callable[[TeamEvent], None] | None = None
) -> SpecialistReport:
    """After a human approves a request, accounting pays it and updates the books."""
    async with shop_mcp:
        found = await shop_mcp.direct_call_tool("get_approval", {"approval_id": approval_id})
        if not found.get("found"):
            raise ValueError(f"No approval {approval_id}.")
        approval = found["approval"]
        if approval["status"] != "approved":
            raise ValueError(f"Approval {approval_id} is '{approval['status']}', not approved.")

        state = TicketState(ticket_id=approval["ticket_id"], on_event=on_event)
        desk = await _system_call(state, "get_ticket", {"ticket_id": state.ticket_id})
        state.date_today = desk["date_today"]
        state.log("system", "run_start", "payment", {"approval": approval})
        task = (
            f"Ticket {state.ticket_id}: a human ({approval['decided_by']}) approved approval "
            f"{approval_id}: {approval['kind']} {approval['ref_id'] or ''} to {approval['payee']} "
            f"for ${approval['amount']:.2f}. Confirm it with get_approval, call pay_approved for "
            f"approval {approval_id} once, and report every table it updated."
        )
        try:
            report = await run_agent(
                get_agent("accounting"), "accounting", task,
                AgentDeps(agent="accounting", state=state),
            )
        except Exception as exc:
            state.log("system", "error", type(exc).__name__, repr(exc))
            raise
        state.log("system", "run_end", "payment", {"approval_id": approval_id})
    return report


def _print_event(event: TeamEvent) -> None:
    detail = event.data if isinstance(event.data, str) else json.dumps(event.data, default=str)
    print(f"[{event.seq:>3}] {event.agent:<16} {event.kind:<14} {event.name}  {detail[:140]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Campus Customs agent team.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Work one ticket.")
    run.add_argument("ticket_id", type=int)
    sub.add_parser("run-all", help="Work every open ticket.")
    pay = sub.add_parser("pay", help="Pay a human-approved request.")
    pay.add_argument("approval_id", type=int)
    args = parser.parse_args()

    if args.command == "pay":
        report = asyncio.run(pay_after_approval(args.approval_id, on_event=_print_event))
        print(report.model_dump_json(indent=2))
        return

    if args.command == "run":
        results = [asyncio.run(run_ticket(args.ticket_id, on_event=_print_event))]
    else:
        results = asyncio.run(run_open_tickets(on_event=_print_event))
    for r in results:
        print(r.decision.model_dump_json(indent=2))


if __name__ == "__main__":
    main()

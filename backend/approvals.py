"""Human approval of payment requests, through the MCP server. No agent can use this.

    python -m backend.approvals list
    python -m backend.approvals approve 3 --by "Store manager"
    python -m backend.approvals reject 3 --by "Store manager"

Approving only marks the request approved; accounting pays it afterwards
(python -m backend.team pay 3). Each decision is appended to the audit trail.
"""

import argparse
import asyncio
from datetime import datetime, timezone

from .audit import append_audit
from .mcp_tools import shop_mcp


async def _call(name: str, args: dict) -> dict:
    async with shop_mcp:
        return await shop_mcp.direct_call_tool(name, args)


def audit_human(approver: str, kind: str, name: str, ticket_id: int | None, data: dict) -> None:
    append_audit({
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "agent": f"human:{approver}",
        "kind": kind,
        "name": name,
        "ticket_id": ticket_id,
        "data": data,
    })


async def decide_async(approval_id: int, approver: str, approve: bool) -> dict:
    """Record a human decision via the MCP decide_approval tool, and audit it."""
    args = {"approval_id": approval_id, "approver": approver, "approve": approve}
    result = await _call("decide_approval", args)
    ticket_id = (result.get("approval") or {}).get("ticket_id")
    audit_human(approver, "human_decision", "decide_approval", ticket_id,
                {"args": args, "result": result})
    return result


def list_pending() -> list[dict]:
    return asyncio.run(_call("list_approvals", {"status": "pending"}))["approvals"]


def decide(approval_id: int, approver: str, approve: bool) -> dict:
    return asyncio.run(decide_async(approval_id, approver, approve))


def main() -> None:
    parser = argparse.ArgumentParser(description="Human approval of payment requests.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Show pending requests.")
    for name in ("approve", "reject"):
        p = sub.add_parser(name)
        p.add_argument("approval_id", type=int)
        p.add_argument("--by", required=True, help="Name of the human deciding.")
    args = parser.parse_args()

    if args.command == "list":
        for a in list_pending():
            print(
                f"#{a['id']} ticket {a['ticket_id']}: {a['kind']} {a['ref_id'] or ''} "
                f"to {a['payee']} ${a['amount']:.2f} (requested by {a['requested_by']}) "
                f"- {a['reason']}"
            )
        return
    print(decide(args.approval_id, args.by, approve=args.command == "approve"))


if __name__ == "__main__":
    main()

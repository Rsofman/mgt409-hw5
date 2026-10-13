"""Connection to the campus-customs MCP server, shared by the whole team.

Every MCP call from an agent passes through `_guard_tool_call`, which:
- enforces the per-ticket tool-call budget,
- stamps who is acting (requested_by / author / paid_by) and which ticket,
  so agents cannot act under another name or on another ticket,
- logs the call and its result to the ticket's event trail.

Each agent only sees the tools in its role (ROLE_TOOLS).
"""

import os
from dataclasses import replace
from typing import Any

from fastmcp.client.transports import PythonStdioTransport
from mcp.client.stdio import get_default_environment
from pydantic_ai import RunContext, ToolDefinition
from pydantic_ai.mcp import CallToolFunc, MCPToolset
from pydantic_ai.toolsets import AbstractToolset

from .config import MCP_SERVER_SCRIPT
from .models import AgentDeps, AgentName

ROLE_TOOLS: dict[AgentName, frozenset[str]] = {
    "boss": frozenset(
        {"get_ticket", "list_open_tickets", "check_cash", "list_board", "list_approvals",
         "discount_options"}
    ),
    "inventory": frozenset(
        {"get_ticket", "check_stock", "list_inventory", "check_vendor_status", "save_draft"}
    ),
    "accounting": frozenset(
        {
            "get_ticket",
            "check_cash",
            "check_invoice",
            "check_rent_due",
            "check_discount",
            "check_stock",
            "check_vendor_status",
            "request_payment_approval",
            "list_approvals",
            "get_approval",
            "pay_approved",
            "list_board",
            "discount_options",
            "save_draft",
        }
    ),
    "facilities": frozenset({"get_ticket", "check_rent_due", "save_draft"}),
    "customer_service": frozenset({"get_ticket", "save_draft"}),
}

# Tools no agent may call, even if a role list is edited by mistake.
# decide_approval is for humans; set_ticket_status is written by the orchestrator
# from the boss's validated decision.
HUMAN_OR_SYSTEM_ONLY = frozenset({"decide_approval", "record_human_decision", "set_ticket_status"})
assert not any(HUMAN_OR_SYSTEM_ONLY & tools for tools in ROLE_TOOLS.values())

# Arguments filled in from the run, never by the model.
_IDENTITY_ARG = {
    "request_payment_approval": "requested_by",
    "pay_approved": "paid_by",
    "save_draft": "author",
    "set_ticket_status": "set_by",
}
_TICKET_SCOPED = {"request_payment_approval", "save_draft"}
_HIDDEN_ARGS = {
    name: {arg} | ({"ticket_id"} if name in _TICKET_SCOPED else set())
    for name, arg in _IDENTITY_ARG.items()
}


async def _guard_tool_call(
    ctx: RunContext[AgentDeps], call_tool: CallToolFunc, name: str, args: dict[str, Any]
) -> Any:
    deps = ctx.deps
    state = deps.state

    if name in HUMAN_OR_SYSTEM_ONLY or name not in ROLE_TOOLS[deps.agent]:
        state.log(deps.agent, "error", name, {"blocked": "tool not allowed for this role", "args": args},
                  depth=deps.depth)
        return {"error": f"{deps.agent} is not allowed to call {name}."}

    if state.tool_calls >= state.max_tool_calls:
        state.log(deps.agent, "limit", name, {"limit": "tool_calls", "max": state.max_tool_calls},
                  depth=deps.depth)
        return {
            "error": f"Tool-call budget for ticket {state.ticket_id} is used up "
            f"({state.max_tool_calls}). Stop and escalate with what you have.",
            "escalate": True,
        }

    args = dict(args)
    if name in _IDENTITY_ARG:
        args[_IDENTITY_ARG[name]] = deps.agent
    if name in _TICKET_SCOPED:
        args["ticket_id"] = state.ticket_id
    if name == "save_draft":
        is_customer_msg = args.get("kind") == "customer_message"
        if is_customer_msg != (deps.agent == "customer_service"):
            state.log(deps.agent, "error", name, {"blocked": "draft kind not allowed", "args": args},
                      depth=deps.depth)
            return {
                "saved": False,
                "error": "Only customer_service writes customer_message drafts, "
                "and customer_service writes only customer_message drafts.",
            }

    state.tool_calls += 1
    state.log(deps.agent, "tool_call", name, args, depth=deps.depth)
    result = await call_tool(name, args)
    state.log(deps.agent, "tool_result", name, result, depth=deps.depth)
    return result


def _hide_stamped_args(
    ctx: RunContext[AgentDeps], tool_defs: list[ToolDefinition]
) -> list[ToolDefinition]:
    """Remove the stamped arguments from the schemas the model sees."""
    prepared = []
    for td in tool_defs:
        hidden = _HIDDEN_ARGS.get(td.name)
        if hidden:
            schema = dict(td.parameters_json_schema)
            schema["properties"] = {
                k: v for k, v in schema.get("properties", {}).items() if k not in hidden
            }
            schema["required"] = [r for r in schema.get("required", []) if r not in hidden]
            td = replace(td, parameters_json_schema=schema)
        prepared.append(td)
    return prepared


# One stdio connection to the server; agents share it through role filters.
# The server can take ~10 s to start on a cold machine, so allow a long handshake.
# CAMPUS_DB_PATH is passed through so a test can point the server at a scratch copy.
_server_env = None
if os.getenv("CAMPUS_DB_PATH"):
    _server_env = {**get_default_environment(), "CAMPUS_DB_PATH": os.environ["CAMPUS_DB_PATH"]}
shop_mcp = MCPToolset(
    PythonStdioTransport(MCP_SERVER_SCRIPT, env=_server_env),
    process_tool_call=_guard_tool_call,
    init_timeout=60,
)


def role_toolset(agent: AgentName) -> AbstractToolset[AgentDeps]:
    allowed = ROLE_TOOLS[agent]
    return shop_mcp.filtered(lambda ctx, td: td.name in allowed).prepared(_hide_stamped_args)

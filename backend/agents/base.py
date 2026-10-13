"""Pieces every agent shares: the delegate tool, shop context, and evidence checks."""

from pydantic_ai import (
    Agent,
    ModelRequest,
    ModelResponse,
    ModelRetry,
    ModelSettings,
    RetryPromptPart,
    RunContext,
    RunUsage,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UsageLimitExceeded,
    UserPromptPart,
)

from ..config import MAX_OUTPUT_TOKENS, MODEL_NAME, get_model, load_prompt
from ..mcp_tools import ROLE_TOOLS, role_toolset
from ..models import AgentDeps, AgentName, Finding, SpecialistReport, TicketState

TEAM_RULES = load_prompt("team_rules")
MODEL_SETTINGS = ModelSettings(max_tokens=MAX_OUTPUT_TOKENS)


async def delegate(ctx: RunContext[AgentDeps], to: AgentName, task: str) -> str:
    """Hand a specific task to a teammate and get their report back.

    Args:
        to: The teammate: boss, inventory, accounting, facilities, or customer_service.
        task: What to do, starting with the ticket id and including every ID needed
            (SKU + size + qty, invoice id, lease id, vendor id, approval id) plus any
            confirmed facts they should use.
    """
    from . import get_agent  # registry imports this module

    deps, state = ctx.deps, ctx.deps.state
    if to == deps.agent:
        raise ModelRetry("You cannot delegate to yourself. Pick a teammate or do the work.")
    if str(state.ticket_id) not in task:
        raise ModelRetry(
            f"Start the task with 'Ticket {state.ticket_id}:' and include every relevant ID."
        )
    if state.delegations >= state.max_delegations or deps.depth + 1 > state.max_depth:
        state.log(deps.agent, "limit", f"delegate->{to}", {"task": task})
        return (
            f"Delegation limit reached for ticket {state.ticket_id} "
            f"({state.delegations}/{state.max_delegations} hand-offs, depth {deps.depth}). "
            "Do not delegate again; finish with what you have and escalate."
        )

    state.delegations += 1
    state.log(deps.agent, "delegation", to, {"task": task}, depth=deps.depth)
    try:
        report = await run_agent(
            get_agent(to), to, task, AgentDeps(agent=to, state=state, depth=deps.depth + 1),
            usage=ctx.usage,
        )
    except UsageLimitExceeded as exc:
        state.log(to, "limit", "usage_limits", str(exc), depth=deps.depth + 1)
        return f"{to} ran out of budget on ticket {state.ticket_id} ({exc}). Escalate."

    state.log(to, "report", f"{to}->{deps.agent}", report.model_dump(mode="json"),
              depth=deps.depth + 1)
    return report.model_dump_json()


def _request_parts(request: ModelRequest) -> list[dict]:
    """What the model was sent this step (the static role prompt is logged once at agent_start)."""
    parts = []
    for p in request.parts:
        if isinstance(p, UserPromptPart):
            parts.append({"type": "user_prompt", "content": p.content})
        elif isinstance(p, ToolReturnPart):
            parts.append({"type": "tool_return", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "content": p.content})
        elif isinstance(p, RetryPromptPart):
            parts.append({"type": "retry", "tool": p.tool_name, "content": p.model_response()})
        else:
            parts.append({"type": type(p).__name__})
    return parts


def _response_summary(response: ModelResponse) -> dict:
    """What the model decided this step: tool calls with arguments, text, and token use."""
    calls, text = [], []
    for p in response.parts:
        if isinstance(p, ToolCallPart):
            calls.append({"tool": p.tool_name, "tool_call_id": p.tool_call_id,
                          "args": p.args_as_dict()})
        elif isinstance(p, TextPart):
            text.append(p.content)
    return {
        "model_name": response.model_name,
        "tool_calls": calls,
        "text": "\n".join(text) or None,
        "finish_reason": response.finish_reason,
        "usage": {"input_tokens": response.usage.input_tokens,
                  "output_tokens": response.usage.output_tokens},
    }


async def run_agent(agent: Agent, name: AgentName, task: str, deps: AgentDeps,
                    usage: RunUsage | None = None):
    """Run one agent loop, logging every step (request, response, output) to the audit trail."""
    state = deps.state
    state.log(name, "agent_start", name,
              {"task": task, "model": MODEL_NAME, "prompt_files": ["team_rules.md", f"{name}.md"],
               "tools": sorted(ROLE_TOOLS[name]) + ["delegate"]},
              depth=deps.depth)
    async with agent.iter(task, deps=deps, usage=usage, usage_limits=state.usage_limits,
                          model_settings=MODEL_SETTINGS) as run:
        step = 0
        async for node in run:
            if Agent.is_model_request_node(node):
                step += 1
                state.log(name, "model_request", f"step {step}", _request_parts(node.request),
                          depth=deps.depth)
            elif Agent.is_call_tools_node(node):
                state.log(name, "model_response", f"step {step}",
                          _response_summary(node.model_response), depth=deps.depth)
        output = run.result.output
        usage_so_far = run.usage  # shared by every agent on this ticket
        state.log(name, "agent_output", name,
                  {"output": output.model_dump(mode="json"),
                   "ticket_usage_so_far": {"requests": usage_so_far.requests,
                                           "input_tokens": usage_so_far.input_tokens,
                                           "output_tokens": usage_so_far.output_tokens}},
                  depth=deps.depth)
    return output


def shop_context(ctx: RunContext[AgentDeps]) -> str:
    state = ctx.deps.state
    return (
        f"You are `{ctx.deps.agent}`. Shop date (desk.date_today): {state.date_today}. "
        f"Ticket: {state.ticket_id}. Budget left on this ticket: "
        f"{state.max_tool_calls - state.tool_calls} tool calls, "
        f"{state.max_delegations - state.delegations} delegations."
    )


def check_findings_trace(state: TicketState, findings: list[Finding]) -> None:
    """Every finding must cite an MCP tool that was actually called on this ticket."""
    called = state.tools_called()
    untraced = [f.fact for f in findings if f.source_tool not in called]
    if untraced:
        raise ModelRetry(
            f"These findings cite tools that were not called on ticket {state.ticket_id}: "
            f"{untraced}. Tools called so far: {sorted(called)}. Cite the tool whose result "
            "contains the fact, call the tool, or drop the finding and list it in missing_data."
        )


def build_specialist(name: AgentName) -> Agent[AgentDeps, SpecialistReport]:
    agent = Agent(
        get_model(),
        name=name,
        deps_type=AgentDeps,
        output_type=SpecialistReport,
        instructions=[TEAM_RULES, load_prompt(name), shop_context],
        toolsets=[role_toolset(name)],
        tools=[delegate],
        retries=2,
    )

    @agent.output_validator
    def _validate(ctx: RunContext[AgentDeps], report: SpecialistReport) -> SpecialistReport:
        state = ctx.deps.state
        report = report.model_copy(update={"agent": ctx.deps.agent, "ticket_id": state.ticket_id})
        check_findings_trace(state, report.findings)
        unknown = set(report.approval_ids) - state.created_approval_ids()
        if unknown:
            raise ModelRetry(f"Approval ids {sorted(unknown)} were not created on this ticket.")
        unknown = set(report.draft_ids) - state.saved_draft_ids()
        if unknown:
            raise ModelRetry(f"Draft ids {sorted(unknown)} were not saved on this ticket.")
        return report

    return agent

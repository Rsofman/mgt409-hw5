"""Boss: classifies and routes tickets, checks evidence, sets status and payment priorities.

Recommends payments but never approves or makes them.
"""

from pydantic_ai import Agent, ModelRetry, RunContext

from ..config import get_model, load_prompt
from ..mcp_tools import role_toolset
from ..models import AgentDeps, BossDecision, TicketStatus
from .base import TEAM_RULES, check_findings_trace, delegate, shop_context

boss_agent = Agent(
    get_model(),
    name="boss",
    deps_type=AgentDeps,
    output_type=BossDecision,
    instructions=[TEAM_RULES, load_prompt("boss"), shop_context],
    toolsets=[role_toolset("boss")],
    tools=[delegate],
    retries=2,
)


@boss_agent.output_validator
def _validate(ctx: RunContext[AgentDeps], decision: BossDecision) -> BossDecision:
    state = ctx.deps.state
    decision = decision.model_copy(update={"ticket_id": state.ticket_id})
    if not decision.findings:
        raise ModelRetry("A decision needs at least one finding traced to an MCP tool.")
    check_findings_trace(state, decision.findings)

    created = state.created_approval_ids()
    cited = {p.approval_id for p in decision.payment_recommendations if p.approval_id is not None}
    if cited - created:
        raise ModelRetry(f"Approval ids {sorted(cited - created)} were not created on this ticket.")
    if decision.status == TicketStatus.AWAITING_APPROVAL and not created:
        raise ModelRetry(
            "Status 'awaiting_approval' needs a pending approval that accounting actually created "
            "with request_payment_approval. Delegate it, or choose another status."
        )
    if decision.customer_draft_id is not None and decision.customer_draft_id not in state.saved_draft_ids():
        raise ModelRetry(f"Draft {decision.customer_draft_id} was not saved on this ticket.")
    if decision.status in (TicketStatus.BLOCKED, TicketStatus.NEEDS_HUMAN) and not decision.escalation_reason:
        raise ModelRetry(f"Status '{decision.status}' needs an escalation_reason.")
    return decision

"""Data types shared by the agent team: agent outputs, run state, and the event trail."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import UsageLimits

from .audit import append_audit
from .config import (
    MAX_DELEGATIONS,
    MAX_DEPTH,
    MAX_MODEL_REQUESTS,
    MAX_TOOL_CALLS,
    MAX_TOTAL_TOKENS,
    MODEL_NAME,
)

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = (
    "boss",
    "inventory",
    "accounting",
    "facilities",
    "customer_service",
)


class TicketType(StrEnum):
    CUSTOMER_ORDER = "customer_order"
    RENT_NOTICE = "rent_notice"
    PRICE_OVERRIDE = "price_override"
    VENDOR_INVOICE = "vendor_invoice"
    OTHER = "other"


class TicketStatus(StrEnum):
    RESOLVED = "resolved"
    AWAITING_APPROVAL = "awaiting_approval"
    BLOCKED = "blocked"
    NEEDS_HUMAN = "needs_human"


class Priority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


# ---------------------------------------------------------------- agent outputs


class Finding(BaseModel):
    """One fact, tied to the MCP tool call that produced it."""

    fact: str = Field(description="The fact in one sentence, with its numbers.")
    source_tool: str = Field(description="The MCP tool whose output contains this fact.")
    source_ids: list[str] = Field(
        default_factory=list,
        description="IDs the fact is about, e.g. 'ticket 101', 'invoice 501', 'CC-TEE-WHITE S'.",
    )


class SpecialistReport(BaseModel):
    """What a specialist hands back to whoever delegated the task."""

    agent: AgentName
    ticket_id: int
    summary: str = Field(description="Two or three sentences answering the task.")
    findings: list[Finding] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(
        default_factory=list,
        description="Anything asked for that the tools could not provide. Flag it; never guess.",
    )
    approval_ids: list[int] = Field(
        default_factory=list, description="Payment approvals requested (still pending)."
    )
    draft_ids: list[int] = Field(default_factory=list, description="Drafts saved to the board.")
    needs_escalation: bool = False
    escalation_reason: str | None = None


class PaymentRecommendation(BaseModel):
    """A payment the boss recommends. Only a human can approve it."""

    kind: Literal["invoice", "rent", "purchase_order"]
    ref_id: int | None = Field(description="Invoice id or lease id; null for purchase orders.")
    payee: str
    amount: float
    pay_order: int = Field(description="1 = pay first when cash cannot cover everything.")
    reason: str
    approval_id: int | None = Field(
        default=None, description="Pending approval id, if accounting already requested one."
    )


class BossDecision(BaseModel):
    """The boss's final call on a ticket."""

    ticket_id: int
    classification: TicketType
    priority: Priority
    status: TicketStatus
    summary: str = Field(description="What was found and decided, in plain language.")
    findings: list[Finding] = Field(
        description="Key facts behind the decision, each traced to an MCP tool call."
    )
    payment_recommendations: list[PaymentRecommendation] = Field(default_factory=list)
    cash_priority_note: str | None = Field(
        default=None, description="Required when cash cannot cover every obligation."
    )
    customer_draft_id: int | None = None
    next_steps: list[str] = Field(default_factory=list)
    escalation_reason: str | None = None


# ---------------------------------------------------------------- run state


EventKind = Literal[
    "run_start",  # orchestrator starts a ticket or payment run
    "agent_start",  # an agent run begins (task, model, prompt files)
    "model_request",  # what was sent to the model this loop step
    "model_response",  # what the model answered: tool calls, text, tokens
    "tool_call",  # MCP tool call, with the arguments actually sent
    "tool_result",  # MCP tool result
    "delegation",  # one agent hands a task to another
    "report",  # a delegated agent's report back
    "agent_output",  # an agent's final validated output
    "limit",  # a budget or limit was hit
    "error",
    "status",  # ticket status written to the board
    "run_end",
]


class TeamEvent(BaseModel):
    """One step in a ticket run, for the audit trail and the dashboard."""

    run_id: str
    seq: int
    ts: str
    shop_date: str
    ticket_id: int
    agent: str
    depth: int | None = None
    kind: EventKind
    name: str
    data: Any = None
    budget: dict[str, int]


@dataclass
class TicketState:
    """Shared by every agent working one ticket: budgets, counters, and the trail."""

    ticket_id: int
    date_today: str = ""
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    audit: bool = True
    max_tool_calls: int = MAX_TOOL_CALLS
    max_delegations: int = MAX_DELEGATIONS
    max_depth: int = MAX_DEPTH
    tool_calls: int = 0
    delegations: int = 0
    events: list[TeamEvent] = field(default_factory=list)
    on_event: Callable[[TeamEvent], None] | None = None
    usage_limits: UsageLimits = field(
        default_factory=lambda: UsageLimits(
            request_limit=MAX_MODEL_REQUESTS, total_tokens_limit=MAX_TOTAL_TOKENS
        )
    )

    def log(
        self, agent: str, kind: EventKind, name: str, data: Any = None, *, depth: int | None = None
    ) -> TeamEvent:
        """Record one step: kept in memory and appended to output/audit_trail.json."""
        event = TeamEvent(
            run_id=self.run_id,
            seq=len(self.events) + 1,
            ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            shop_date=self.date_today,
            ticket_id=self.ticket_id,
            agent=agent,
            depth=depth,
            kind=kind,
            name=name,
            data=data,
            budget={
                "tool_calls_used": self.tool_calls,
                "tool_calls_max": self.max_tool_calls,
                "delegations_used": self.delegations,
                "delegations_max": self.max_delegations,
            },
        )
        self.events.append(event)
        if self.audit:
            append_audit({"model": MODEL_NAME, **event.model_dump(mode="json")})
        if self.on_event is not None:
            self.on_event(event)
        return event

    def tool_results(self, name: str | None = None) -> list[dict]:
        """Results of MCP tool calls made on this ticket, optionally for one tool."""
        return [
            e.data
            for e in self.events
            if e.kind == "tool_result" and (name is None or e.name == name)
            and isinstance(e.data, dict)
        ]

    def tools_called(self) -> set[str]:
        return {e.name for e in self.events if e.kind == "tool_result"}

    def created_approval_ids(self) -> set[int]:
        return {
            r["approval_id"]
            for r in self.tool_results("request_payment_approval")
            if r.get("created")
        }

    def saved_draft_ids(self) -> set[int]:
        return {r["draft_id"] for r in self.tool_results("save_draft") if r.get("saved")}


@dataclass
class AgentDeps:
    """Per-agent-run dependencies: who is acting, on which ticket, how deep in the chain."""

    agent: AgentName
    state: TicketState
    depth: int = 0


class TicketRunResult(BaseModel):
    run_id: str
    ticket_id: int
    decision: BossDecision
    tool_calls_used: int
    delegations_used: int
    events: list[TeamEvent]

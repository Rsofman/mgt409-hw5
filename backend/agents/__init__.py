"""The Campus Customs agent team. Any agent can delegate to any other through `delegate`."""

from pydantic_ai import Agent

from ..models import AgentName
from .accounting import accounting_agent
from .boss import boss_agent
from .customer_service import customer_service_agent
from .facilities import facilities_agent
from .inventory import inventory_agent

TEAM: dict[AgentName, Agent] = {
    "boss": boss_agent,
    "inventory": inventory_agent,
    "accounting": accounting_agent,
    "facilities": facilities_agent,
    "customer_service": customer_service_agent,
}


def get_agent(name: AgentName) -> Agent:
    return TEAM[name]

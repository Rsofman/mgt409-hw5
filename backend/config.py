"""Shared settings: paths, the one allowed model, and per-ticket limits."""

import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
MCP_SERVER_SCRIPT = PROJECT_ROOT / "mcp_server" / "server.py"
ORIGINAL_DB = PROJECT_ROOT / "data" / "campus_customs.db"
WORKING_DB = PROJECT_ROOT / "data" / "campus_customs_new.db"
AUDIT_TRAIL = Path(os.getenv("CAMPUS_AUDIT_PATH", PROJECT_ROOT / "output" / "audit_trail.json"))

# The key lives in a local .env (this folder or the course folder); never in source.
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT.parent / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# The assignment requires gpt-6-luna for every agent, so there is no override.
MODEL_NAME = "gpt-6-luna"

# Per-ticket budgets, shared by every agent that works the ticket.
MAX_TOOL_CALLS = 30  # MCP tool calls
MAX_DELEGATIONS = 8  # hand-offs between agents
MAX_DEPTH = 3  # boss -> specialist -> specialist -> specialist
MAX_MODEL_REQUESTS = 60  # backstop across all nested agent runs
MAX_TOTAL_TOKENS = 300_000  # input + output tokens across the whole ticket
MAX_OUTPUT_TOKENS = 6_000  # per model response (includes reasoning)


@cache
def get_model() -> OpenAIResponsesModel:
    """gpt-6-luna through Portkey's OpenAI-compatible endpoint (Responses API).

    The Chat Completions route rejects function tools for this model, so the
    Responses model is used.
    """
    client = AsyncOpenAI(
        api_key=os.environ["PORTKEY_API_KEY"],
        base_url=os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1"),
        default_headers={"x-portkey-provider": os.getenv("PORTKEY_PROVIDER", "openai")},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")

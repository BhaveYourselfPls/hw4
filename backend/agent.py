"""The Campus Customs merch agent (Pydantic AI).

Wiring, in one place:

* **Model** — OpenAI through the Portkey gateway. `PORTKEY_API_KEY` is read from
  the nearest `.env` at or above the project folder, never hard-coded.
* **Instructions** — `prompts/prompt.md`, loaded from disk so the voice and
  safety rules can be edited without touching Python.
* **Tools** — the five catalogue functions in `tools.py`.
* **Output** — `ChatReply`, so every turn comes back as prose *plus* the
  structured product list the UI renders as cards.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from models import ChatDeps, ChatReply
from tools import AGENT_TOOLS

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
PROMPT_PATH = BACKEND_DIR / "prompts" / "prompt.md"

# Walk up from the project folder so a shared .env a few levels above (the
# course root) works without copying the key into this homework.
for folder in [PROJECT_ROOT, *PROJECT_ROOT.parents]:
    env_file = folder / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

# gpt-6-luna is the course default and the cheap end of the rate card.
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-6-luna")
PORTKEY_BASE_URL = os.getenv("PORTKEY_BASE_URL", "https://api.portkey.ai/v1").rstrip("/")


def api_key_is_set() -> bool:
    """Whether a key is present — used by /api/health, without exposing it."""
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "PORTKEY_API_KEY is missing. Put it in a .env in this project or a parent folder."
        )
    return key


def load_instructions() -> str:
    if not PROMPT_PATH.exists():
        raise RuntimeError(f"Prompt file not found at {PROMPT_PATH}")
    return PROMPT_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """Portkey-backed model client, built once per process.

    Uses the Responses API: the luna models reject tools plus reasoning settings
    on chat/completions.
    """
    client = AsyncOpenAI(
        api_key=require_api_key(),
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


@lru_cache(maxsize=1)
def get_agent() -> Agent[ChatDeps, ChatReply]:
    """The configured agent, built lazily and cached.

    Lazy on purpose: importing this module must not fail when the API key is
    absent, so the catalogue endpoints still serve and /api/health can report
    the problem instead of the whole app refusing to start.
    """
    agent = Agent(
        build_model(),
        deps_type=ChatDeps,
        output_type=ChatReply,
        instructions=load_instructions(),
        tools=AGENT_TOOLS,
        retries=2,
    )

    @agent.instructions
    def who_is_shopping(ctx: RunContext[ChatDeps]) -> str:
        """Who the assistant is talking to.

        Only a first name reaches the model — never an email, an id, a password
        hash, or anything else from the users table.
        """
        if not ctx.deps.user_name:
            return (
                "The shopper is browsing as a guest, so this conversation is not "
                "being saved. Do not ask them to sign in unless they bring it up "
                "or ask about saved history."
            )

        first = ctx.deps.user_name.split(" ")[0]
        if ctx.deps.returning:
            return (
                f"The shopper is signed in. Their first name is {first}, and the "
                "turns above are their own earlier conversation with you, loaded "
                "from their account. Treat it as something you both remember: "
                "pick up where it left off, refer back to it when relevant, and "
                "do not re-introduce yourself. Their conversation is saved to "
                "their account."
            )
        return (
            f"The shopper is signed in and their first name is {first}. This is "
            "their first conversation with you. Greet them by name once, "
            "naturally, then get on with helping."
        )

    @agent.instructions
    def where_are_they(ctx: RunContext[ChatDeps]) -> str:
        """What the shopper is looking at while they type.

        This is what lets "do you have this in pink?" or "is this in large?"
        resolve to a real product instead of a guess.
        """
        if ctx.deps.page_product_id:
            return (
                f"The shopper is currently viewing the {ctx.deps.page_product_name} "
                f"product page (product_id: {ctx.deps.page_product_id}). When they "
                'say "this", "it" or "that one" without naming something else, they '
                "mean this product — look it up directly rather than searching. If "
                "they clearly mean a different item, follow their lead instead."
            )
        if ctx.deps.page_label:
            return f"The shopper is browsing {ctx.deps.page_label}."
        return ""

    @agent.instructions
    def what_size(ctx: RunContext[ChatDeps]) -> str:
        """The size the shopper saved on the site.

        Lets answers be about what actually fits them, rather than listing
        stock for five sizes they will never buy.
        """
        if not ctx.deps.preferred_size:
            return ""
        return (
            f"The shopper has saved {ctx.deps.preferred_size} as their size. "
            "Check availability in that size first and lead with it. If it is "
            "sold out, say so and offer a similar item that is in stock in "
            f"{ctx.deps.preferred_size}. Do not ask what size they wear."
        )

    return agent

"""Assemble the PostPilot deep agent.

Architecture (LangChain `deepagents`):

    Orchestrator (deep agent)
      ├─ tools: generate_image, post_to_twitter, post_to_instagram, post_to_linkedin
      ├─ built-in deepagents tools: write_todos (planning) + virtual filesystem
      └─ sub-agents (isolated context windows):
            ├─ twitter_writer
            ├─ instagram_writer
            └─ linkedin_writer

The three `post_to_*` tools are registered in `interrupt_on`, which wires
deepagents' Human-in-the-Loop middleware: the graph PAUSES before each publish
and surfaces the exact payload for a human to approve / edit / reject. Pair the
agent with a checkpointer so the pause can be resumed across turns.
"""

from __future__ import annotations

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from . import prompts
from .config import settings
from .schemas import ALL_PLATFORMS, Platform
from .tools import (
    POSTING_TOOLS,
    POSTING_TOOL_NAMES,
    generate_image,
)

_WRITER_PROMPTS = {
    "twitter": prompts.TWITTER_WRITER_PROMPT,
    "instagram": prompts.INSTAGRAM_WRITER_PROMPT,
    "linkedin": prompts.LINKEDIN_WRITER_PROMPT,
}

_WRITER_DESCRIPTIONS = {
    "twitter": "Drafts punchy Twitter/X copy under 280 characters with 1-3 hashtags.",
    "instagram": "Drafts warm, visual Instagram captions with discovery hashtags.",
    "linkedin": "Drafts professional, insight-led LinkedIn posts with a soft CTA.",
}


def _approval_config() -> dict:
    """InterruptOnConfig: every publish needs approve / edit / reject."""
    return {
        "allowed_decisions": ["approve", "edit", "reject"],
    }


def build_agent(
    platforms: tuple[Platform, ...] = ALL_PLATFORMS,
    *,
    checkpointer=None,
    model: str | None = None,
):
    """Create the PostPilot deep agent for the requested platforms.

    Args:
        platforms: Which networks to target (sub-agents + interrupts are scoped
            to these).
        checkpointer: A LangGraph checkpointer. Required for the human-approval
            interrupts to be resumable. Defaults to an in-memory saver.
        model: Override the chat model string.

    Returns:
        A compiled LangGraph agent (`CompiledStateGraph`).
    """
    checkpointer = checkpointer if checkpointer is not None else InMemorySaver()

    subagents = [
        {
            "name": f"{p}_writer",
            "description": _WRITER_DESCRIPTIONS[p],
            "system_prompt": _WRITER_PROMPTS[p],
        }
        for p in platforms
    ]

    tools = [generate_image] + [POSTING_TOOLS[p] for p in platforms]

    interrupt_on = {POSTING_TOOL_NAMES[p]: _approval_config() for p in platforms}

    return create_deep_agent(
        model=model or settings.model,
        tools=tools,
        system_prompt=prompts.ORCHESTRATOR_PROMPT,
        subagents=subagents,
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )

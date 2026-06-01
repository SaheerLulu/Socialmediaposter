"""Assemble the DealDesk sales & marketing deep agent.

Mirrors the social poster's design: a deepagents orchestrator with a copywriter
sub-agent and the two outreach send-tools gated behind a human-approval
interrupt. Pair with a checkpointer so approvals are resumable.
"""

from __future__ import annotations

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from ..config import settings
from . import prompts
from .tools import ALL_TOOLS, SEND_TOOL_NAMES


def _approval_config() -> dict:
    return {"allowed_decisions": ["approve", "edit", "reject"]}


def build_sales_agent(*, checkpointer=None, model: str | None = None):
    """Create the DealDesk agent with HITL approval on every send."""
    checkpointer = checkpointer if checkpointer is not None else InMemorySaver()

    copywriter = {
        "name": "copywriter",
        "description": "Drafts a single highly personalized outreach message for one prospect.",
        "system_prompt": prompts.COPYWRITER_PROMPT,
    }

    interrupt_on = {name: _approval_config() for name in SEND_TOOL_NAMES}

    return create_deep_agent(
        model=model or settings.model,
        tools=ALL_TOOLS,
        system_prompt=prompts.SALES_AGENT_PROMPT,
        subagents=[copywriter],
        interrupt_on=interrupt_on,
        checkpointer=checkpointer,
    )

"""Drive the PostPilot agent through its plan → draft → approve → publish loop.

The human-approval checkpoint is the heart of the product: when the agent is
ready to publish, the graph interrupts and exposes the *exact* final payload
(caption + image) for each platform. The helpers here let a CLI or web UI read
those pending posts and resume the graph with the human's decisions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from langgraph.types import Command


@dataclass
class PendingPost:
    """A final, ready-to-publish post awaiting a human decision."""

    index: int
    tool_name: str
    platform: str
    caption: str
    image_path: str | None
    description: str = ""


_TOOL_TO_PLATFORM = {
    "post_to_twitter": "twitter",
    "post_to_instagram": "instagram",
    "post_to_linkedin": "linkedin",
}


def new_thread_config() -> dict[str, Any]:
    """A fresh LangGraph config with a unique thread id (one per campaign)."""
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


def _interrupts(result: dict[str, Any]) -> list[Any]:
    raw = result.get("__interrupt__") or []
    return list(raw)


def pending_posts(result: dict[str, Any]) -> list[PendingPost]:
    """Extract the final posts the agent is waiting to publish, if any."""
    interrupts = _interrupts(result)
    if not interrupts:
        return []
    value = interrupts[0].value  # HITLRequest
    requests = value.get("action_requests", []) if isinstance(value, dict) else []
    posts: list[PendingPost] = []
    for i, req in enumerate(requests):
        args = req.get("args", {})
        posts.append(
            PendingPost(
                index=i,
                tool_name=req.get("name", ""),
                platform=_TOOL_TO_PLATFORM.get(req.get("name", ""), req.get("name", "")),
                caption=args.get("caption", ""),
                image_path=args.get("image_path"),
                description=req.get("description", ""),
            )
        )
    return posts


def is_waiting_for_approval(result: dict[str, Any]) -> bool:
    return bool(_interrupts(result))


def approve() -> dict[str, str]:
    return {"type": "approve"}


def reject(message: str = "Rejected by reviewer.") -> dict[str, str]:
    return {"type": "reject", "message": message}


def edit(tool_name: str, caption: str, image_path: str | None) -> dict[str, Any]:
    args: dict[str, Any] = {"caption": caption}
    if image_path is not None:
        args["image_path"] = image_path
    return {"type": "edit", "edited_action": {"name": tool_name, "args": args}}


def start_campaign(agent, brief: str, config: dict[str, Any]) -> dict[str, Any]:
    """Run the agent from the brief until it either finishes or asks to publish."""
    return agent.invoke({"messages": [{"role": "user", "content": brief}]}, config=config)


def resume_with_decisions(
    agent, decisions: list[dict[str, Any]], config: dict[str, Any]
) -> dict[str, Any]:
    """Resume a paused campaign with one decision per pending post."""
    return agent.invoke(Command(resume={"decisions": decisions}), config=config)


def final_message(result: dict[str, Any]) -> str:
    """Best-effort text of the agent's last spoken message."""
    for msg in reversed(result.get("messages", [])):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip() and getattr(msg, "type", "") == "ai":
            return content
    return ""

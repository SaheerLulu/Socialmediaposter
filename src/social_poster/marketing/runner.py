"""Drive the DealDesk agent through draft → approve → send."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from langgraph.types import Command


@dataclass
class PendingSend:
    """An outreach message awaiting a human decision."""

    index: int
    tool_name: str
    channel: str
    lead_id: str
    subject: str
    body: str


_TOOL_TO_CHANNEL = {
    "send_outreach_email": "email",
    "send_outreach_whatsapp": "whatsapp",
}


def new_thread_config() -> dict[str, Any]:
    return {"configurable": {"thread_id": uuid.uuid4().hex}}


def _interrupts(result: dict[str, Any]) -> list[Any]:
    return list(result.get("__interrupt__") or [])


def is_waiting_for_approval(result: dict[str, Any]) -> bool:
    return bool(_interrupts(result))


def pending_sends(result: dict[str, Any]) -> list[PendingSend]:
    interrupts = _interrupts(result)
    if not interrupts:
        return []
    value = interrupts[0].value
    requests = value.get("action_requests", []) if isinstance(value, dict) else []
    out: list[PendingSend] = []
    for i, req in enumerate(requests):
        args = req.get("args", {})
        out.append(
            PendingSend(
                index=i,
                tool_name=req.get("name", ""),
                channel=_TOOL_TO_CHANNEL.get(req.get("name", ""), req.get("name", "")),
                lead_id=args.get("lead_id", ""),
                subject=args.get("subject", ""),
                body=args.get("body", ""),
            )
        )
    return out


def approve() -> dict[str, str]:
    return {"type": "approve"}


def reject(message: str = "Rejected by reviewer.") -> dict[str, str]:
    return {"type": "reject", "message": message}


def edit(send: PendingSend, subject: str, body: str) -> dict[str, Any]:
    args: dict[str, Any] = {"lead_id": send.lead_id, "body": body}
    if send.tool_name == "send_outreach_email":
        args["subject"] = subject
    return {"type": "edit", "edited_action": {"name": send.tool_name, "args": args}}


def start_run(agent, instruction: str, config: dict[str, Any]) -> dict[str, Any]:
    return agent.invoke({"messages": [{"role": "user", "content": instruction}]}, config=config)


def resume_with_decisions(agent, decisions: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    return agent.invoke(Command(resume={"decisions": decisions}), config=config)


def final_message(result: dict[str, Any]) -> str:
    for msg in reversed(result.get("messages", [])):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip() and getattr(msg, "type", "") == "ai":
            return content
    return ""


DEFAULT_INSTRUCTION = (
    "Run an outbound campaign now: ground yourself in the business profile, pull "
    "the leads that are due, and draft + send one personalized message to each."
)

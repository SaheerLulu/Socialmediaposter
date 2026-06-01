"""Typed data structures shared across the agent, tools, and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Platform = Literal["twitter", "instagram", "linkedin"]
ALL_PLATFORMS: tuple[Platform, ...] = ("twitter", "instagram", "linkedin")

# Hard platform limits the content-writer sub-agents must respect.
PLATFORM_LIMITS: dict[Platform, int] = {
    "twitter": 280,
    "instagram": 2200,
    "linkedin": 3000,
}


@dataclass
class DraftPost:
    """A single platform-specific draft awaiting human approval."""

    platform: Platform
    caption: str
    hashtags: list[str] = field(default_factory=list)
    image_path: str | None = None

    def rendered(self) -> str:
        tags = " ".join(self.hashtags)
        return f"{self.caption}\n\n{tags}".strip()


@dataclass
class PostResult:
    """The outcome of attempting to publish to a platform."""

    platform: Platform
    ok: bool
    permalink: str | None = None
    detail: str = ""
    dry_run: bool = False

"""Central configuration for the agentic social media poster.

All secrets and tunables are read from environment variables so the same code
runs locally, in CI, and in production. A `.env` file is loaded automatically
if `python-dotenv` is installed (see `.env.example`).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:  # optional convenience: load a local .env if present
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
OUTBOX_DIR = PROJECT_ROOT / "outbox"
ASSETS_DIR.mkdir(exist_ok=True)
OUTBOX_DIR.mkdir(exist_ok=True)


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """Runtime settings resolved from the environment."""

    # The chat model that drives every agent / sub-agent. Any string that
    # `langchain.chat_models.init_chat_model` understands works here.
    model: str = field(
        default_factory=lambda: os.getenv("SOCIAL_POSTER_MODEL", "claude-sonnet-4-5-20250929")
    )

    # When DRY_RUN is on, posting tools and image generation never touch a real
    # network API: posts are written to the local ./outbox and a fake permalink
    # is returned. This lets the whole agentic flow run end-to-end with zero
    # credentials, which is the default so the demo "just works".
    dry_run: bool = field(default_factory=lambda: _flag("SOCIAL_POSTER_DRY_RUN", True))

    # Image generation provider: "auto" picks the first provider with a key,
    # falling back to a locally rendered placeholder. Force one with
    # "openai", "gemini", or "placeholder".
    image_provider: str = field(
        default_factory=lambda: os.getenv("SOCIAL_POSTER_IMAGE_PROVIDER", "auto")
    )

    # --- Platform credentials (only needed when dry_run is False) --------- #
    twitter_bearer_token: str | None = field(default_factory=lambda: os.getenv("TWITTER_BEARER_TOKEN"))
    twitter_api_key: str | None = field(default_factory=lambda: os.getenv("TWITTER_API_KEY"))
    twitter_api_secret: str | None = field(default_factory=lambda: os.getenv("TWITTER_API_SECRET"))
    twitter_access_token: str | None = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_TOKEN"))
    twitter_access_secret: str | None = field(default_factory=lambda: os.getenv("TWITTER_ACCESS_SECRET"))

    instagram_user_id: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_USER_ID"))
    instagram_access_token: str | None = field(default_factory=lambda: os.getenv("INSTAGRAM_ACCESS_TOKEN"))

    linkedin_access_token: str | None = field(default_factory=lambda: os.getenv("LINKEDIN_ACCESS_TOKEN"))
    linkedin_author_urn: str | None = field(default_factory=lambda: os.getenv("LINKEDIN_AUTHOR_URN"))

    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    google_api_key: str | None = field(
        default_factory=lambda: os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    )

    def resolved_image_provider(self) -> str:
        """Decide which image backend to use given configured keys."""
        if self.image_provider != "auto":
            return self.image_provider
        if self.openai_api_key:
            return "openai"
        if self.google_api_key:
            return "gemini"
        return "placeholder"


settings = Settings()

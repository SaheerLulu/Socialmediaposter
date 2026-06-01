"""Shared helpers for the platform posting tools."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..config import OUTBOX_DIR


def write_to_outbox(platform: str, caption: str, image_path: str | None) -> str:
    """Persist a simulated post to ./outbox and return a fake permalink.

    Used in DRY_RUN mode so the full agentic flow can be exercised with no
    credentials. The outbox doubles as an auditable record of what *would*
    have been published.
    """
    post_id = uuid.uuid4().hex[:12]
    record = {
        "id": post_id,
        "platform": platform,
        "caption": caption,
        "image_path": image_path,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
    }
    out = OUTBOX_DIR / f"{platform}-{post_id}.json"
    out.write_text(json.dumps(record, indent=2))
    return f"https://example.test/{platform}/{post_id}"


def require(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(
            f"Missing credential '{name}'. Set it in the environment or enable "
            f"SOCIAL_POSTER_DRY_RUN=true to simulate posting."
        )
    return value


def ensure_image(image_path: str | None) -> Path:
    if not image_path:
        raise RuntimeError("An image is required for this platform.")
    p = Path(image_path)
    if not p.exists():
        raise RuntimeError(f"Image file not found: {image_path}")
    return p

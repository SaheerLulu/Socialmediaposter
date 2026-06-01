"""Shared dry-run staging for outreach channels."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ..config import MARKETING_OUTBOX


def stage(channel: str, to: str, payload: dict) -> str:
    msg_id = uuid.uuid4().hex[:12]
    record = {
        "id": msg_id,
        "channel": channel,
        "to": to,
        "staged_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": True,
        **payload,
    }
    (MARKETING_OUTBOX / f"{channel}-{msg_id}.json").write_text(json.dumps(record, indent=2))
    return msg_id

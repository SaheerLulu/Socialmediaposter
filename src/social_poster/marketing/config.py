"""Marketing-module configuration, resolved from the environment."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from ..config import PROJECT_ROOT, _flag  # reuse base helpers

DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
MARKETING_OUTBOX = PROJECT_ROOT / "outbox" / "marketing"
MARKETING_OUTBOX.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class MarketingSettings:
    # When true (default), outreach is simulated and written to the marketing
    # outbox instead of actually emailing / messaging anyone.
    dry_run: bool = field(default_factory=lambda: _flag("MARKETING_DRY_RUN", True))

    # Compliance guardrails ------------------------------------------------- #
    # Only contact leads with a lawful basis. Strongly recommended: keep True.
    require_opt_in: bool = field(default_factory=lambda: _flag("MARKETING_REQUIRE_OPT_IN", True))
    unsubscribe_url: str = field(
        default_factory=lambda: os.getenv("MARKETING_UNSUBSCRIBE_URL", "https://example.com/unsubscribe")
    )
    # Throttling: protects deliverability and respects platform limits.
    max_per_run: int = field(default_factory=lambda: int(os.getenv("MARKETING_MAX_PER_RUN", "25")))
    max_per_day: int = field(default_factory=lambda: int(os.getenv("MARKETING_MAX_PER_DAY", "200")))
    min_seconds_between_sends: float = field(
        default_factory=lambda: float(os.getenv("MARKETING_MIN_SECONDS_BETWEEN_SENDS", "3"))
    )
    # Quiet hours (local 24h clock): no outreach sent within this window.
    quiet_start_hour: int = field(default_factory=lambda: int(os.getenv("MARKETING_QUIET_START", "21")))
    quiet_end_hour: int = field(default_factory=lambda: int(os.getenv("MARKETING_QUIET_END", "8")))
    # Follow-up cadence.
    followup_days: int = field(default_factory=lambda: int(os.getenv("MARKETING_FOLLOWUP_DAYS", "3")))
    max_touches: int = field(default_factory=lambda: int(os.getenv("MARKETING_MAX_TOUCHES", "3")))

    # Scheduler ------------------------------------------------------------- #
    # Seconds between autonomous campaign runs (default 1h). The daemon runs
    # "24/7" by sleeping this long between batches, honoring quiet hours/caps.
    run_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("MARKETING_RUN_INTERVAL_SECONDS", "3600"))
    )
    # If True, the scheduler auto-approves drafts (fully autonomous). Default
    # False: drafts await human approval. Only enable once you trust the copy.
    autonomous: bool = field(default_factory=lambda: _flag("MARKETING_AUTONOMOUS", False))

    # Storage --------------------------------------------------------------- #
    # Backend for the CRM: "sql" (Postgres/SQLAlchemy) or "json" (file).
    # Defaults to "sql" when DATABASE_URL is set, else "json".
    db_backend: str = field(
        default_factory=lambda: os.getenv(
            "MARKETING_DB_BACKEND", "sql" if os.getenv("DATABASE_URL") else "json"
        )
    )

    # Files ----------------------------------------------------------------- #
    leads_path: Path = field(default_factory=lambda: DATA_DIR / "leads.json")
    business_profile_path: Path = field(
        default_factory=lambda: Path(
            os.getenv("MARKETING_BUSINESS_PROFILE", str(DATA_DIR / "business_profile.yaml"))
        )
    )

    # Email (SMTP) ---------------------------------------------------------- #
    smtp_host: str | None = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: str | None = field(default_factory=lambda: os.getenv("SMTP_USER"))
    smtp_password: str | None = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))
    smtp_from: str | None = field(default_factory=lambda: os.getenv("SMTP_FROM"))
    smtp_use_tls: bool = field(default_factory=lambda: _flag("SMTP_USE_TLS", True))

    # WhatsApp -------------------------------------------------------------- #
    # provider: "meta" (Cloud API) or "twilio"
    whatsapp_provider: str = field(
        default_factory=lambda: os.getenv("WHATSAPP_PROVIDER", "meta")
    )
    whatsapp_token: str | None = field(default_factory=lambda: os.getenv("WHATSAPP_TOKEN"))
    whatsapp_phone_id: str | None = field(default_factory=lambda: os.getenv("WHATSAPP_PHONE_ID"))
    # Twilio
    twilio_sid: str | None = field(default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID"))
    twilio_auth: str | None = field(default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN"))
    twilio_from: str | None = field(default_factory=lambda: os.getenv("TWILIO_WHATSAPP_FROM"))


marketing_settings = MarketingSettings()

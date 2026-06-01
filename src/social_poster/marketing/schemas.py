"""Typed data structures for the sales & marketing module."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Literal

Channel = Literal["email", "whatsapp"]
ALL_CHANNELS: tuple[Channel, ...] = ("email", "whatsapp")


class Consent(str, Enum):
    """Lawful basis for contacting a lead.

    Outreach is only allowed to leads whose consent is OPT_IN (or, when the
    operator asserts a lawful basis, LEGITIMATE_INTEREST). NONE and
    UNSUBSCRIBED are never contacted.
    """

    OPT_IN = "opt_in"
    LEGITIMATE_INTEREST = "legitimate_interest"
    NONE = "none"
    UNSUBSCRIBED = "unsubscribed"


class LeadStatus(str, Enum):
    NEW = "new"
    QUEUED = "queued"
    CONTACTED = "contacted"
    REPLIED = "replied"
    CONVERTED = "converted"
    BOUNCED = "bounced"
    DO_NOT_CONTACT = "do_not_contact"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Lead:
    """A prospect in the CRM."""

    id: str
    name: str = ""
    email: str | None = None
    whatsapp: str | None = None  # E.164, e.g. +14155550123
    company: str = ""
    role: str = ""
    notes: str = ""
    tags: list[str] = field(default_factory=list)
    consent: str = Consent.NONE.value
    status: str = LeadStatus.NEW.value
    touches: int = 0  # how many outreach messages sent
    last_contacted_at: str | None = None
    next_followup_at: str | None = None
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Lead":
        known = {k: v for k, v in d.items() if k in cls.__annotations__}
        return cls(**known)


@dataclass
class OutreachDraft:
    """A channel-specific message drafted for a single lead, pre-approval."""

    lead_id: str
    channel: Channel
    subject: str = ""  # email only
    body: str = ""

    def preview(self) -> str:
        head = f"[{self.channel}] " + (f"Subject: {self.subject}\n" if self.subject else "")
        return head + self.body


@dataclass
class SendResult:
    lead_id: str
    channel: Channel
    ok: bool
    detail: str = ""
    dry_run: bool = False

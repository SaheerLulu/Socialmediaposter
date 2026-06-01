"""A Postgres/SQL-backed CRM store with the same interface as the JSON store.

Drop-in replacement for `LeadStore`: the agent, tools, and scheduler use it
unchanged. Selected via `MARKETING_DB_BACKEND=sql` (or automatically when
`DATABASE_URL` is set).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import marketing_settings
from .db import ActivityRow, ConsentRow, LeadRow, get_session_factory
from .schemas import Consent, Lead, LeadStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_lead(row: LeadRow) -> Lead:
    return Lead(
        id=row.id, name=row.name, email=row.email, whatsapp=row.whatsapp,
        company=row.company, role=row.role, notes=row.notes, tags=list(row.tags or []),
        consent=row.consent, status=row.status, touches=row.touches,
        last_contacted_at=row.last_contacted_at.isoformat() if row.last_contacted_at else None,
        next_followup_at=row.next_followup_at.isoformat() if row.next_followup_at else None,
        created_at=row.created_at.isoformat() if row.created_at else _now().isoformat(),
    )


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


class SqlLeadStore:
    """SQLAlchemy-backed CRM store (Postgres in prod, SQLite for dev/tests)."""

    def __init__(self) -> None:
        self.Session = get_session_factory()

    # --- reads ------------------------------------------------------------- #
    def all(self) -> list[Lead]:
        with self.Session() as s:
            return [_to_lead(r) for r in s.scalars(select(LeadRow)).all()]

    def get(self, lead_id: str) -> Lead | None:
        with self.Session() as s:
            row = s.get(LeadRow, lead_id)
            return _to_lead(row) if row else None

    # --- writes ------------------------------------------------------------ #
    def upsert(self, lead: Lead, *, activity: str | None = None) -> Lead:
        with self.Session() as s:
            row = s.get(LeadRow, lead.id)
            if row is None:
                row = LeadRow(id=lead.id)
                s.add(row)
            row.name = lead.name
            row.email = lead.email
            row.whatsapp = lead.whatsapp
            row.company = lead.company
            row.role = lead.role
            row.notes = lead.notes
            row.tags = list(lead.tags or [])
            row.consent = lead.consent
            row.status = lead.status
            row.touches = lead.touches
            row.last_contacted_at = _parse(lead.last_contacted_at)
            row.next_followup_at = _parse(lead.next_followup_at)
            if activity:
                s.add(ActivityRow(lead_id=lead.id, kind=activity))
            s.commit()
            return _to_lead(row)

    def record_consent(self, lead_id: str, basis: str, source: str = "", evidence: str = "") -> None:
        with self.Session() as s:
            s.add(ConsentRow(lead_id=lead_id, basis=basis, source=source, evidence=evidence))
            s.commit()

    def log_activity(self, lead_id: str, kind: str, channel: str = "", detail: str = "") -> None:
        with self.Session() as s:
            s.add(ActivityRow(lead_id=lead_id, kind=kind, channel=channel, detail=detail))
            s.commit()

    # --- consent / suppression -------------------------------------------- #
    def unsubscribe(self, lead_id: str) -> None:
        with self.Session() as s:
            row = s.get(LeadRow, lead_id)
            if row:
                row.consent = Consent.UNSUBSCRIBED.value
                row.status = LeadStatus.DO_NOT_CONTACT.value
                s.add(ConsentRow(lead_id=lead_id, basis=Consent.UNSUBSCRIBED.value,
                                 source="unsubscribe", evidence="suppressed"))
                s.add(ActivityRow(lead_id=lead_id, kind="unsubscribe"))
                s.commit()

    def is_contactable(self, lead: Lead) -> bool:
        if lead.consent == Consent.UNSUBSCRIBED.value:
            return False
        if marketing_settings.require_opt_in and lead.consent == Consent.NONE.value:
            return False
        if lead.status in (LeadStatus.DO_NOT_CONTACT.value, LeadStatus.CONVERTED.value,
                           LeadStatus.BOUNCED.value):
            return False
        if lead.touches >= marketing_settings.max_touches:
            return False
        return True

    def _followup_due(self, lead: Lead) -> bool:
        if lead.next_followup_at is None:
            return True
        due = _parse(lead.next_followup_at)
        return due is None or due <= _now()

    def due_leads(self, channel: str | None = None, limit: int | None = None) -> list[Lead]:
        out: list[Lead] = []
        for lead in self.all():
            if not self.is_contactable(lead):
                continue
            if channel == "email" and not lead.email:
                continue
            if channel == "whatsapp" and not lead.whatsapp:
                continue
            if not (lead.email or lead.whatsapp):
                continue
            if not self._followup_due(lead):
                continue
            out.append(lead)
        out.sort(key=lambda l: (l.touches, l.created_at))
        return out[:limit] if limit is not None else out

    def record_touch(self, lead_id: str) -> None:
        with self.Session() as s:
            row = s.get(LeadRow, lead_id)
            if not row:
                return
            row.touches += 1
            row.last_contacted_at = _now()
            row.next_followup_at = _now() + timedelta(days=marketing_settings.followup_days)
            row.status = LeadStatus.CONTACTED.value
            s.add(ActivityRow(lead_id=lead_id, kind="touch"))
            s.commit()

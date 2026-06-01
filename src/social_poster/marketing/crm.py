"""A simple JSON-backed CRM: leads, consent, suppression, and eligibility.

This is intentionally file-based so the demo runs with zero infrastructure.
Swap `LeadStore` for a database-backed implementation in production.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import marketing_settings
from .schemas import Consent, Lead, LeadStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


class LeadStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or marketing_settings.leads_path
        self._leads: dict[str, Lead] = {}
        self.load()

    # --- persistence ------------------------------------------------------- #
    def load(self) -> None:
        if self.path.exists():
            raw = json.loads(self.path.read_text() or "[]")
            self._leads = {d["id"]: Lead.from_dict(d) for d in raw}
        else:
            self._leads = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([l.to_dict() for l in self._leads.values()], indent=2))

    # --- CRUD -------------------------------------------------------------- #
    def all(self) -> list[Lead]:
        return list(self._leads.values())

    def get(self, lead_id: str) -> Lead | None:
        return self._leads.get(lead_id)

    def upsert(self, lead: Lead) -> Lead:
        self._leads[lead.id] = lead
        self.save()
        return lead

    # --- consent / suppression -------------------------------------------- #
    def unsubscribe(self, lead_id: str) -> None:
        lead = self._leads.get(lead_id)
        if lead:
            lead.consent = Consent.UNSUBSCRIBED.value
            lead.status = LeadStatus.DO_NOT_CONTACT.value
            self.save()

    def is_contactable(self, lead: Lead) -> bool:
        """A lead may be contacted only with a lawful basis and capacity left."""
        if lead.consent in (Consent.UNSUBSCRIBED.value, Consent.NONE.value):
            if marketing_settings.require_opt_in:
                # NONE blocked when opt-in required; UNSUBSCRIBED always blocked.
                if lead.consent == Consent.UNSUBSCRIBED.value:
                    return False
                return lead.consent != Consent.NONE.value
            if lead.consent == Consent.UNSUBSCRIBED.value:
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
        try:
            return datetime.fromisoformat(lead.next_followup_at) <= _now()
        except ValueError:
            return True

    def due_leads(self, channel: str | None = None, limit: int | None = None) -> list[Lead]:
        """Eligible leads that are due for an outreach touch right now."""
        out: list[Lead] = []
        for lead in self._leads.values():
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
        if limit is not None:
            out = out[:limit]
        return out

    def record_touch(self, lead_id: str) -> None:
        lead = self._leads.get(lead_id)
        if not lead:
            return
        lead.touches += 1
        lead.last_contacted_at = _now().isoformat()
        lead.next_followup_at = (_now() + timedelta(days=marketing_settings.followup_days)).isoformat()
        lead.status = LeadStatus.CONTACTED.value
        self.save()


def make_store():
    """Return the configured CRM store: SQL (Postgres) or JSON."""
    if marketing_settings.db_backend == "sql":
        from .store_sql import SqlLeadStore

        return SqlLeadStore()
    return LeadStore()


def seed_example_leads(store) -> None:
    """Populate a few opted-in demo leads if the store is empty."""
    if store.all():
        return
    demo = [
        Lead(id="L001", name="Priya Nair", email="priya@acmeretail.example",
             whatsapp="+919800000001", company="Acme Retail", role="Head of Marketing",
             consent=Consent.OPT_IN.value, tags=["retail", "warm"],
             notes="Downloaded our pricing guide at a trade show."),
        Lead(id="L002", name="Tom Becker", email="tom@brightcafe.example",
             company="Bright Cafe", role="Owner", consent=Consent.OPT_IN.value,
             tags=["food", "smb"], notes="Signed up for the newsletter."),
        Lead(id="L003", name="Lena Cruz", whatsapp="+34600000003", company="Cruz Studios",
             role="Founder", consent=Consent.OPT_IN.value, tags=["agency"],
             notes="Asked for a callback via the website form."),
    ]
    for lead in demo:
        store.upsert(lead)

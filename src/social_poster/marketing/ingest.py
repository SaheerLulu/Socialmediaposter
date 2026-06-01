"""Import contacts you already own into the CRM — safely.

This is the compliant way to populate the CRM: bring in lists you collected
yourself (customers, opt-ins, your existing CRM export). Every row carries a
consent basis; rows without a lawful basis are stored as `none` and will NOT be
contacted while `MARKETING_REQUIRE_OPT_IN` is on.

It does NOT scrape third parties. Garbage in is your responsibility — if you
mark someone `opt_in`, you must actually hold that consent.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .schemas import Consent, Lead

# accepted column aliases -> Lead field (keys are normalized: lower, spaces/
# hyphens collapsed to underscores)
_ALIASES = {
    "name": "name", "full_name": "name", "fullname": "name", "contact": "name", "contact_name": "name",
    "email": "email", "e_mail": "email", "email_address": "email",
    "whatsapp": "whatsapp", "whatsapp_number": "whatsapp", "phone": "whatsapp",
    "mobile": "whatsapp", "number": "whatsapp", "phone_number": "whatsapp",
    "company": "company", "organization": "company", "organisation": "company", "account": "company",
    "role": "role", "title": "role", "job_title": "role", "position": "role",
    "notes": "notes", "note": "notes",
    "consent": "consent", "consent_basis": "consent", "lawful_basis": "consent",
    "tags": "tags", "tag": "tags",
}

_VALID_CONSENT = {c.value for c in Consent}


def _norm_key(k: str) -> str:
    return k.strip().lower().replace(" ", "_").replace("-", "_")


def _stable_id(email: str | None, whatsapp: str | None, name: str) -> str:
    key = (email or "").strip().lower() or (whatsapp or "").strip() or name.strip().lower()
    return "C" + hashlib.sha1(key.encode()).hexdigest()[:11]


def _normalize_row(raw: dict) -> dict:
    out: dict = {}
    for k, v in raw.items():
        if k is None:
            continue
        field = _ALIASES.get(_norm_key(k))
        if not field or v is None:
            continue
        out[field] = v.strip() if isinstance(v, str) else v
    return out


def normalize_lead(raw: dict, *, source: str, default_consent: str | None) -> tuple[Lead | None, str]:
    """Turn a raw row into a Lead, or (None, reason) if it can't be imported."""
    row = _normalize_row(raw)
    email = (row.get("email") or "").strip() or None
    whatsapp = (row.get("whatsapp") or "").strip() or None
    name = (row.get("name") or "").strip()
    if not (email or whatsapp):
        return None, "no email or whatsapp"

    consent = (row.get("consent") or default_consent or Consent.NONE.value).strip().lower()
    if consent not in _VALID_CONSENT:
        consent = Consent.NONE.value

    tags = row.get("tags")
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.replace(";", ",").split(",") if t.strip()]

    lead = Lead(
        id=_stable_id(email, whatsapp, name),
        name=name, email=email, whatsapp=whatsapp,
        company=row.get("company", ""), role=row.get("role", ""),
        notes=row.get("notes", ""), tags=tags or [], consent=consent,
    )
    return lead, ""


def import_rows(
    rows: Iterable[dict], store, *, source: str, default_consent: str | None = None
) -> dict:
    """Import an iterable of raw dict rows. Returns a summary."""
    imported = updated = skipped = 0
    reasons: list[str] = []
    for raw in rows:
        lead, why = normalize_lead(raw, source=source, default_consent=default_consent)
        if lead is None:
            skipped += 1
            reasons.append(why)
            continue
        existed = store.get(lead.id) is not None
        # record source on the lead via notes-less field path
        if hasattr(store, "upsert"):
            store.upsert(lead, activity="imported") if _accepts_activity(store) else store.upsert(lead)
        # consent + audit trail when the backend supports it
        if lead.consent in (Consent.OPT_IN.value, Consent.LEGITIMATE_INTEREST.value):
            if hasattr(store, "record_consent"):
                store.record_consent(lead.id, lead.consent, source=source, evidence="import")
        updated += int(existed)
        imported += int(not existed)
    return {"imported": imported, "updated": updated, "skipped": skipped, "reasons": reasons[:10]}


def _accepts_activity(store) -> bool:
    import inspect

    try:
        return "activity" in inspect.signature(store.upsert).parameters
    except (TypeError, ValueError):
        return False


def import_csv(path: str | Path, store, *, source: str = "", default_consent: str | None = None) -> dict:
    path = Path(path)
    source = source or f"csv:{path.name}"
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return import_rows(csv.DictReader(fh), store, source=source, default_consent=default_consent)


def import_json(path: str | Path, store, *, source: str = "", default_consent: str | None = None) -> dict:
    path = Path(path)
    source = source or f"json:{path.name}"
    data = json.loads(path.read_text())
    if isinstance(data, dict):
        data = data.get("contacts") or data.get("leads") or [data]
    return import_rows(data, store, source=source, default_consent=default_consent)


def capture_lead(
    store,
    *,
    name: str,
    email: str | None = None,
    whatsapp: str | None = None,
    company: str = "",
    consent: str = Consent.OPT_IN.value,
    source: str = "web_form",
    evidence: str = "",
) -> Lead:
    """Lead-intake for opt-in / contact-form submissions (records consent)."""
    lead, why = normalize_lead(
        {"name": name, "email": email, "whatsapp": whatsapp, "company": company, "consent": consent},
        source=source, default_consent=consent,
    )
    if lead is None:
        raise ValueError(f"cannot capture lead: {why}")
    if _accepts_activity(store):
        store.upsert(lead, activity="captured")
    else:
        store.upsert(lead)
    if hasattr(store, "record_consent") and consent in (
        Consent.OPT_IN.value, Consent.LEGITIMATE_INTEREST.value
    ):
        store.record_consent(lead.id, consent, source=source, evidence=evidence or source)
    return lead

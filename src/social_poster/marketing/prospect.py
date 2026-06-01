"""Prospect leads from companies' OWN websites (B2B).

This extracts a company's *published business* contact details — the role-based
address they put on their site to be contacted on (info@, sales@, hello@…), the
switchboard number, the company name and blurb — and turns each company into a
CRM lead.

Scope & guardrails:
  * Same-domain crawl only, robots.txt honored, small page budget, polite delay.
  * Prefers **role-based** mailboxes; named-individual emails are skipped by
    default (`include_personal=False`) to avoid collecting personal data.
  * Imported under a **legitimate-interest** basis (the appropriate lawful basis
    for B2B), never as "opt_in" — and every email still carries an unsubscribe.
  * Scraped phone numbers are stored as notes, NOT as WhatsApp targets (a
    switchboard line is not a consented messaging channel).

You remain responsible for your legitimate-interest assessment, for honoring
opt-outs, and for the terms/robots of the sites you crawl.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from .enrich import crawl_site
from .schemas import Consent, Lead

# mailbox prefixes that denote a company/role inbox rather than a person
ROLE_PREFIXES = {
    "info", "sales", "hello", "contact", "contacts", "support", "marketing",
    "admin", "office", "team", "enquiries", "inquiries", "press", "media",
    "business", "partnerships", "partner", "bd", "hi", "mail", "help", "service",
}

_PHONE_RE = re.compile(r"(?:(?:\+|00)\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?){2,4}\d{2,4}")


def _is_role(email: str) -> bool:
    return email.split("@", 1)[0].strip().lower() in ROLE_PREFIXES


def _company_name(title: str, domain: str) -> str:
    if title:
        # take the brand part of a "Brand | tagline" / "Brand - tagline" title
        name = re.split(r"[|\-–—:·]", title)[0].strip()
        if name:
            return name
    return domain.split(".")[0].capitalize()


def _extract_phones(text: str, limit: int = 3) -> list[str]:
    seen: list[str] = []
    for m in _PHONE_RE.findall(text or ""):
        cand = re.sub(r"[\s.\-()]", "", m)
        if 8 <= len(re.sub(r"\D", "", cand)) <= 15 and cand not in seen:
            seen.append(cand)
        if len(seen) >= limit:
            break
    return seen


def discover_company(url: str) -> dict:
    """Crawl one company site and return its published business contact info."""
    data = crawl_site(url)
    domain = data["domain"]
    emails = data["company_emails"]  # already same-domain, deduped
    role_emails = [e for e in emails if _is_role(e)]
    other_emails = [e for e in emails if not _is_role(e)]
    text = " ".join(p["text"] for p in data["pages"])
    return {
        "company": _company_name(data["title"], domain),
        "domain": domain,
        "website": data["base_url"],
        "role_emails": role_emails,
        "other_emails": other_emails,
        "phones": _extract_phones(text),
        "description": (data["pages"][0]["text"][:280] if data["pages"] else ""),
    }


def _lead_id(domain: str, email: str | None) -> str:
    key = (email or domain).lower()
    return "W" + hashlib.sha1(key.encode()).hexdigest()[:11]


def lead_from_company(disc: dict, *, consent: str, include_personal: bool) -> Lead | None:
    """Build a CRM lead from a discovered company, or None if no usable email."""
    email = None
    if disc["role_emails"]:
        email = disc["role_emails"][0]
    elif include_personal and disc["other_emails"]:
        email = disc["other_emails"][0]
    if not email:
        return None

    phone_note = f" | phone(s): {', '.join(disc['phones'])}" if disc["phones"] else ""
    return Lead(
        id=_lead_id(disc["domain"], email),
        name="",  # company/role inbox — no individual
        email=email,
        whatsapp=None,  # never message a scraped switchboard number
        company=disc["company"],
        role="",
        notes=(disc["description"] + phone_note).strip(),
        tags=["website-prospect", disc["domain"]],
        consent=consent,
    )


def prospect_companies(
    urls: list[str],
    store,
    *,
    consent: str = Consent.LEGITIMATE_INTEREST.value,
    include_personal: bool = False,
    preview: bool = False,
) -> dict:
    """Discover and (unless preview) import leads from a list of company sites."""
    found, imported, skipped = [], 0, 0
    for url in urls:
        try:
            disc = discover_company(url)
        except Exception as exc:  # network / parse failure — skip that site
            skipped += 1
            found.append({"url": url, "error": str(exc)})
            continue
        lead = lead_from_company(disc, consent=consent, include_personal=include_personal)
        if lead is None:
            skipped += 1
            found.append({"url": url, "company": disc["company"], "note": "no usable business email"})
            continue
        found.append({"url": url, "company": disc["company"], "email": lead.email,
                      "phones": disc["phones"]})
        if not preview:
            existed = store.get(lead.id) is not None
            if hasattr(store, "upsert"):
                try:
                    store.upsert(lead, activity="prospected")
                except TypeError:
                    store.upsert(lead)
            if not existed and hasattr(store, "record_consent") and consent in (
                Consent.OPT_IN.value, Consent.LEGITIMATE_INTEREST.value
            ):
                store.record_consent(lead.id, consent,
                                     source=f"website:{disc['domain']}",
                                     evidence="published business contact on company site")
            imported += int(not existed)
    return {"discovered": len([f for f in found if f.get("email")]),
            "imported": imported, "skipped": skipped, "details": found}


def read_url_list(path: str) -> list[str]:
    """Read newline-separated URLs from a file (blank lines / # comments ignored)."""
    from pathlib import Path

    lines = Path(path).read_text().splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]

"""Tests for company-website prospecting (offline; crawl is monkeypatched)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def test_role_email_and_company_name_helpers():
    from social_poster.marketing import prospect

    assert prospect._is_role("info@acme.com")
    assert prospect._is_role("Sales@Acme.com")
    assert not prospect._is_role("jane.doe@acme.com")
    assert prospect._company_name("Acme Co | Widgets for all", "acme.com") == "Acme Co"
    assert prospect._company_name("", "acme.com") == "Acme"


def test_phone_extraction():
    from social_poster.marketing import prospect

    phones = prospect._extract_phones("Call us on +44 20 7946 0958 or (555) 123-4567 today")
    assert any("442079460958" in p for p in phones)


def test_lead_from_company_prefers_role_and_no_whatsapp():
    from social_poster.marketing import prospect

    disc = {
        "company": "Acme Co", "domain": "acme.com", "website": "https://acme.com",
        "role_emails": ["info@acme.com"], "other_emails": ["jane@acme.com"],
        "phones": ["+442079460958"], "description": "We make widgets.",
    }
    lead = prospect.lead_from_company(disc, consent="legitimate_interest", include_personal=False)
    assert lead.email == "info@acme.com"
    assert lead.whatsapp is None  # never message a scraped switchboard
    assert lead.consent == "legitimate_interest"
    assert "website-prospect" in lead.tags and "442079460958" in lead.notes
    assert lead.name == ""  # role inbox, not a person


def test_lead_from_company_skips_personal_by_default():
    from social_poster.marketing import prospect

    disc = {"company": "X", "domain": "x.com", "website": "https://x.com",
            "role_emails": [], "other_emails": ["bob@x.com"], "phones": [], "description": ""}
    assert prospect.lead_from_company(disc, consent="legitimate_interest", include_personal=False) is None
    assert prospect.lead_from_company(disc, consent="legitimate_interest", include_personal=True) is not None


def test_prospect_companies_imports(monkeypatch, tmp_path=None):
    from social_poster.marketing import prospect
    from social_poster.marketing.crm import LeadStore

    fake = {
        "https://acme.com": {
            "company": "Acme Co", "domain": "acme.com", "website": "https://acme.com",
            "role_emails": ["sales@acme.com"], "other_emails": [],
            "phones": ["+15551234567"], "description": "Widgets.",
        }
    }
    monkeypatch.setattr(prospect, "discover_company", lambda url: fake[url])
    store = LeadStore(path=Path("/tmp/prospect_test.json"))
    if store.path.exists():
        store.path.unlink()
        store = LeadStore(path=Path("/tmp/prospect_test.json"))
    summary = prospect.prospect_companies(["https://acme.com"], store)
    assert summary["imported"] == 1 and summary["discovered"] == 1
    lead = next(l for l in store.all() if l.company == "Acme Co")
    assert lead.email == "sales@acme.com" and lead.consent == "legitimate_interest"


if __name__ == "__main__":
    # tiny monkeypatch shim so this runs without pytest
    class _MP:
        def setattr(self, obj, name, val):
            setattr(obj, name, val)

    fns = [(k, v) for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for name, fn in fns:
        import inspect

        kwargs = {}
        if "monkeypatch" in inspect.signature(fn).parameters:
            kwargs["monkeypatch"] = _MP()
        fn(**kwargs)
        print(f"ok  {name}")
    print(f"\n{len(fns)} passed")

"""Tests for the Postgres/SQL CRM backend, importer, and lead intake.

Runs against a temporary SQLite database (SQLAlchemy code is identical on
Postgres). No LLM or network required.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Point the DB at a throwaway SQLite file BEFORE the engine is created.
_DB = Path("/tmp/crm_pytest.db")
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


def _csv(tmp: Path) -> Path:
    tmp.write_text(
        "Full Name,Email,Phone,Company,Title,Consent,Tags\n"
        "Dana Lee,dana@owned.example,+15551230001,Lee Co,COO,opt_in,saas;warm\n"
        "Raj Patel,raj@owned.example,,Patel Labs,CTO,legitimate_interest,saas\n"
        "Nobody,,,Ghost Inc,,opt_in,\n"
        "Sam Stone,sam@owned.example,,Stone Studio,Owner,none,agency\n"
    )
    return tmp


def test_init_and_upsert_roundtrip():
    from social_poster.marketing.db import init_db
    from social_poster.marketing.schemas import Consent, Lead
    from social_poster.marketing.store_sql import SqlLeadStore

    init_db()
    store = SqlLeadStore()
    store.upsert(Lead(id="X1", name="Ada", email="ada@owned.example", consent=Consent.OPT_IN.value))
    got = store.get("X1")
    assert got and got.name == "Ada" and got.consent == "opt_in"


def test_csv_import_consent_and_dedupe():
    from social_poster.marketing.ingest import import_csv
    from social_poster.marketing.store_sql import SqlLeadStore

    store = SqlLeadStore()
    path = _csv(Path("/tmp/crm_pytest_contacts.csv"))
    summary = import_csv(path, store, source="unit-test")
    assert summary["imported"] == 3 and summary["skipped"] == 1  # Nobody has no contact

    by_name = {l.name: l for l in store.all()}
    assert by_name["Dana Lee"].consent == "opt_in"
    assert by_name["Raj Patel"].consent == "legitimate_interest"
    # consent=none stays, but is not contactable while opt-in is required
    assert not store.is_contactable(by_name["Sam Stone"])
    # contactable ones show up as due
    due_ids = {l.id for l in store.due_leads(channel="email")}
    assert by_name["Dana Lee"].id in due_ids

    # re-import updates rather than duplicates
    again = import_csv(path, store, source="unit-test")
    assert again["updated"] == 3 and again["imported"] == 0


def test_audit_trail_and_unsubscribe():
    from sqlalchemy import func, select

    from social_poster.marketing.db import ActivityRow, ConsentRow, get_session_factory
    from social_poster.marketing.store_sql import SqlLeadStore

    store = SqlLeadStore()
    S = get_session_factory()
    with S() as s:
        assert s.scalar(select(func.count()).select_from(ConsentRow)) >= 2  # opt_in + legit_interest
        assert s.scalar(select(func.count()).select_from(ActivityRow)) >= 1

    dana = next(l for l in store.all() if l.name == "Dana Lee")
    store.unsubscribe(dana.id)
    assert not store.is_contactable(store.get(dana.id))


def test_capture_lead_records_consent():
    from social_poster.marketing.ingest import capture_lead
    from social_poster.marketing.store_sql import SqlLeadStore

    store = SqlLeadStore()
    lead = capture_lead(store, name="Web Visitor", email="visitor@signup.example",
                        consent="opt_in", source="web_form", evidence="form ts")
    assert store.get(lead.id).consent == "opt_in"


if __name__ == "__main__":
    # Definition order (these tests share one DB and build on each other).
    fns = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")

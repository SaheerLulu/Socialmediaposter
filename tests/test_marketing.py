"""Tests for the DealDesk sales & marketing module (no LLM call required)."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

os.environ.setdefault("MARKETING_DRY_RUN", "true")
os.environ.setdefault("MARKETING_REQUIRE_OPT_IN", "true")


def _tmp_store(tmp_name="leads_test.json"):
    from social_poster.marketing.crm import LeadStore, seed_example_leads

    path = Path("/tmp") / tmp_name
    if path.exists():
        path.unlink()
    store = LeadStore(path=path)
    seed_example_leads(store)
    return store


def test_business_profile_loads_from_yaml():
    from social_poster.marketing.business import load_business_profile

    bp = load_business_profile(Path("data/business_profile.example.yaml"))
    assert bp.name and bp.cta
    assert "Company:" in bp.as_brief()


def test_crm_eligibility_and_suppression():
    from social_poster.marketing.schemas import Consent

    store = _tmp_store("leads_elig.json")
    due_ids = {l.id for l in store.due_leads()}
    assert {"L001", "L002", "L003"} <= due_ids  # all opted-in & new

    store.unsubscribe("L001")
    assert "L001" not in {l.id for l in store.due_leads()}

    # a lead with no consent is blocked when opt-in is required
    lead = store.get("L002")
    lead.consent = Consent.NONE.value
    store.upsert(lead)
    assert not store.is_contactable(store.get("L002"))


def test_governor_quiet_hours_and_caps():
    from social_poster.marketing.governor import SendGovernor

    g = SendGovernor()
    # default quiet window is 21:00-08:00 -> 23:00 is quiet, 12:00 is not
    assert g.in_quiet_hours(datetime(2026, 1, 1, 23, 0))
    assert not g.in_quiet_hours(datetime(2026, 1, 1, 12, 0))


def test_dry_run_send_records_touch_and_followup():
    store = _tmp_store("leads_send.json")
    # bypass quiet hours for a deterministic send
    from social_poster.marketing import tools
    from social_poster.marketing.governor import governor

    tools._store = store  # point the tool at our temp store
    governor.in_quiet_hours = lambda now=None: False  # type: ignore

    out = tools.send_outreach_email.invoke(
        {"lead_id": "L001", "subject": "Hi", "body": "Hello Priya"}
    )
    assert "staged" in out.lower() or "sent" in out.lower()
    lead = store.get("L001")
    assert lead.touches == 1 and lead.next_followup_at and lead.status == "contacted"


def test_runner_parses_pending_sends():
    from social_poster.marketing import runner

    fake = SimpleNamespace(value={"action_requests": [
        {"name": "send_outreach_email",
         "args": {"lead_id": "L001", "subject": "Hi", "body": "Hello"}},
        {"name": "send_outreach_whatsapp",
         "args": {"lead_id": "L003", "body": "Hey there"}},
    ]})
    sends = runner.pending_sends({"__interrupt__": [fake]})
    assert [s.channel for s in sends] == ["email", "whatsapp"]
    assert sends[0].subject == "Hi" and sends[1].lead_id == "L003"


def test_sales_agent_wires_hitl_on_sends():
    from social_poster.marketing.agent import build_sales_agent

    agent = build_sales_agent(model="claude-sonnet-4-5-20250929")
    nodes = list(agent.get_graph().nodes.keys())
    assert any("HumanInTheLoop" in n for n in nodes)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")

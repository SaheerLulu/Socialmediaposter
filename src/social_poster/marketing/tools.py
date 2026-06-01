"""LangChain tools the sales & marketing agent uses.

The two send tools (`send_outreach_email`, `send_outreach_whatsapp`) are the
ones gated behind the human-approval interrupt. They also re-check eligibility
and throttling at execution time (defense in depth — never trust the model to
honor consent on its own).
"""

from __future__ import annotations

import json

from langchain_core.tools import tool

from .business import load_business_profile
from .channels import send_email_message, send_whatsapp_message
from .config import marketing_settings
from .crm import make_store
from .governor import governor

# Shared, lazily-loaded CRM store for the running process (SQL or JSON backend).
_store = None


def get_store():
    global _store
    if _store is None:
        _store = make_store()
    return _store


@tool
def get_business_profile() -> str:
    """Return a briefing of who we are, what we sell, our tone, and our CTA.

    Call this first so every message is grounded in our actual business.
    """
    return load_business_profile().as_brief()


@tool
def find_due_leads(channel: str = "", limit: int = 10) -> str:
    """List eligible prospects who are due for an outreach touch right now.

    Only returns leads with a lawful basis to contact (opt-in / legitimate
    interest), not unsubscribed, under the touch cap, and past their follow-up
    date. Suppressed and converted leads are never returned.

    Args:
        channel: Optional filter, "email" or "whatsapp".
        limit: Max leads to return (capped at the per-run limit).
    """
    limit = min(limit, marketing_settings.max_per_run)
    leads = get_store().due_leads(channel=channel or None, limit=limit)
    rows = [
        {
            "id": l.id, "name": l.name, "company": l.company, "role": l.role,
            "email": l.email, "whatsapp": l.whatsapp, "tags": l.tags,
            "touches": l.touches, "notes": l.notes,
        }
        for l in leads
    ]
    if not rows:
        return "No eligible leads are due right now."
    return json.dumps(rows, indent=2)


def _guard(lead_id: str, channel: str):
    store = get_store()
    lead = store.get(lead_id)
    if lead is None:
        return None, f"No lead with id {lead_id}."
    if not store.is_contactable(lead):
        return None, f"Lead {lead_id} is not contactable (consent/suppression/cap)."
    ok, why = governor.can_send()
    if not ok:
        return None, f"Send blocked: {why}."
    return lead, ""


@tool
def send_outreach_email(lead_id: str, subject: str, body: str) -> str:
    """Send a personalized outreach email to a lead. Requires human approval.

    Args:
        lead_id: The CRM id of the recipient (from find_due_leads).
        subject: Email subject line.
        body: Plain-text email body (an unsubscribe footer is added for you).
    """
    lead, err = _guard(lead_id, "email")
    if err:
        return err
    if not lead.email:
        return f"Lead {lead_id} has no email address."
    governor.wait_for_slot()
    result = send_email_message(lead_id, lead.email, subject, body)
    if result.ok:
        governor.record()
        get_store().record_touch(lead_id)
    return result.detail


@tool
def send_outreach_whatsapp(lead_id: str, body: str) -> str:
    """Send a personalized WhatsApp message to a lead. Requires human approval.

    Args:
        lead_id: The CRM id of the recipient (from find_due_leads).
        body: The message text. Keep it short, personal, and compliant.
    """
    lead, err = _guard(lead_id, "whatsapp")
    if err:
        return err
    if not lead.whatsapp:
        return f"Lead {lead_id} has no WhatsApp number."
    governor.wait_for_slot()
    result = send_whatsapp_message(lead_id, lead.whatsapp, body)
    if result.ok:
        governor.record()
        get_store().record_touch(lead_id)
    return result.detail


@tool
def mark_lead(lead_id: str, status: str) -> str:
    """Update a lead's status: replied | converted | do_not_contact | unsubscribed.

    Use this to record outcomes so we never re-contact converted or
    unsubscribed people.
    """
    store = get_store()
    lead = store.get(lead_id)
    if lead is None:
        return f"No lead with id {lead_id}."
    status = status.strip().lower()
    if status == "unsubscribed":
        store.unsubscribe(lead_id)
        return f"Lead {lead_id} unsubscribed and suppressed."
    lead.status = status
    store.upsert(lead)
    return f"Lead {lead_id} marked {status}."


SEND_TOOL_NAMES = ["send_outreach_email", "send_outreach_whatsapp"]
ALL_TOOLS = [
    get_business_profile,
    find_due_leads,
    send_outreach_email,
    send_outreach_whatsapp,
    mark_lead,
]

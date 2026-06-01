"""WhatsApp outreach via Meta Cloud API or Twilio, with dry-run staging.

WhatsApp requires recipients to have opted in, and business-initiated
conversations must use a pre-approved message template. Keep DRY_RUN on until
your templates are approved and your opt-in records are in order.
"""

from __future__ import annotations

from ..config import marketing_settings
from ..schemas import SendResult
from ._outbox import stage


def send_whatsapp_message(lead_id: str, to_number: str, body: str) -> SendResult:
    if marketing_settings.dry_run:
        stage("whatsapp", to_number, {"lead_id": lead_id, "body": body})
        return SendResult(lead_id, "whatsapp", ok=True, dry_run=True,
                          detail=f"[DRY RUN] whatsapp staged for {to_number}")

    provider = marketing_settings.whatsapp_provider.lower()
    if provider == "twilio":
        return _send_twilio(lead_id, to_number, body)
    return _send_meta(lead_id, to_number, body)


def _send_meta(lead_id: str, to_number: str, body: str) -> SendResult:
    import requests

    s = marketing_settings
    if not (s.whatsapp_token and s.whatsapp_phone_id):
        return SendResult(lead_id, "whatsapp", ok=False,
                          detail="Meta WhatsApp not configured (WHATSAPP_TOKEN, WHATSAPP_PHONE_ID)")
    url = f"https://graph.facebook.com/v21.0/{s.whatsapp_phone_id}/messages"
    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {s.whatsapp_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number.lstrip("+"),
                "type": "text",
                "text": {"body": body},
            },
            timeout=30,
        )
        r.raise_for_status()
        return SendResult(lead_id, "whatsapp", ok=True, detail=f"sent to {to_number}")
    except Exception as exc:  # pragma: no cover
        return SendResult(lead_id, "whatsapp", ok=False, detail=f"send failed: {exc}")


def _send_twilio(lead_id: str, to_number: str, body: str) -> SendResult:
    import requests

    s = marketing_settings
    if not (s.twilio_sid and s.twilio_auth and s.twilio_from):
        return SendResult(lead_id, "whatsapp", ok=False,
                          detail="Twilio not configured (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM)")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_sid}/Messages.json"
    try:
        r = requests.post(
            url,
            data={"From": f"whatsapp:{s.twilio_from}", "To": f"whatsapp:{to_number}", "Body": body},
            auth=(s.twilio_sid, s.twilio_auth),
            timeout=30,
        )
        r.raise_for_status()
        return SendResult(lead_id, "whatsapp", ok=True, detail=f"sent to {to_number}")
    except Exception as exc:  # pragma: no cover
        return SendResult(lead_id, "whatsapp", ok=False, detail=f"send failed: {exc}")

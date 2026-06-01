"""Outreach channels: email (SMTP) and WhatsApp (Meta Cloud API / Twilio)."""

from __future__ import annotations

from .email_channel import send_email_message
from .whatsapp_channel import send_whatsapp_message

__all__ = ["send_email_message", "send_whatsapp_message"]

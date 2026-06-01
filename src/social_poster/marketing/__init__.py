"""DealDesk — the sales & marketing module for PostPilot.

Understands your business, finds eligible prospects, drafts personalized
outreach, and (after human approval) sends via email and WhatsApp — on a 24/7
cadence with consent, suppression, rate-limit, and quiet-hour guardrails.
"""

from __future__ import annotations

from .agent import build_sales_agent
from .business import BusinessProfile, load_business_profile
from .crm import LeadStore
from .schemas import ALL_CHANNELS, Consent, Lead, LeadStatus

__all__ = [
    "build_sales_agent",
    "BusinessProfile",
    "load_business_profile",
    "LeadStore",
    "Lead",
    "Consent",
    "LeadStatus",
    "ALL_CHANNELS",
]

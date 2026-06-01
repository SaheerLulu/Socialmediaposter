"""Load and represent the business profile the sales agent reasons about."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import marketing_settings


@dataclass
class BusinessProfile:
    """Everything the agent needs to understand who we are and what we sell."""

    name: str = "Your Company"
    one_liner: str = ""
    description: str = ""
    products: list[str] = field(default_factory=list)
    value_props: list[str] = field(default_factory=list)
    ideal_customer: str = ""
    target_industries: list[str] = field(default_factory=list)
    tone: str = "warm, concise, professional, helpful"
    website: str = ""
    cta: str = "Reply to this message or book a quick call."
    sender_name: str = ""
    sender_title: str = ""

    def as_brief(self) -> str:
        """A compact, prompt-ready briefing string."""
        lines = [
            f"Company: {self.name}",
            f"One-liner: {self.one_liner}" if self.one_liner else "",
            f"What we do: {self.description}" if self.description else "",
            f"Products/Services: {', '.join(self.products)}" if self.products else "",
            f"Value propositions: {'; '.join(self.value_props)}" if self.value_props else "",
            f"Ideal customer: {self.ideal_customer}" if self.ideal_customer else "",
            f"Target industries: {', '.join(self.target_industries)}" if self.target_industries else "",
            f"Website: {self.website}" if self.website else "",
            f"Preferred tone: {self.tone}",
            f"Call to action: {self.cta}",
            f"Sender: {self.sender_name}{', ' + self.sender_title if self.sender_title else ''}",
        ]
        return "\n".join(x for x in lines if x)


def _load_yaml_or_json(path: Path) -> dict:
    text = path.read_text()
    if path.suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text) or {}
        except ModuleNotFoundError:
            # Minimal fallback: allow JSON content in a .yaml file if PyYAML
            # isn't installed.
            return json.loads(text)
    return json.loads(text)


def load_business_profile(path: Path | None = None) -> BusinessProfile:
    """Load the business profile from disk, or return sensible defaults."""
    path = path or marketing_settings.business_profile_path
    if not path.exists():
        return BusinessProfile()
    data = _load_yaml_or_json(path)
    known = {k: v for k, v in data.items() if k in BusinessProfile.__annotations__}
    return BusinessProfile(**known)

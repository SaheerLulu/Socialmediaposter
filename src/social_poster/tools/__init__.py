"""Tool registry for the social media poster agent."""

from __future__ import annotations

from .image_gen import generate_image
from .instagram import post_to_instagram
from .linkedin import post_to_linkedin
from .twitter import post_to_twitter

# Tools that publish externally — these are gated behind human approval.
POSTING_TOOLS = {
    "twitter": post_to_twitter,
    "instagram": post_to_instagram,
    "linkedin": post_to_linkedin,
}

POSTING_TOOL_NAMES = {
    "twitter": "post_to_twitter",
    "instagram": "post_to_instagram",
    "linkedin": "post_to_linkedin",
}

__all__ = [
    "generate_image",
    "post_to_twitter",
    "post_to_instagram",
    "post_to_linkedin",
    "POSTING_TOOLS",
    "POSTING_TOOL_NAMES",
]

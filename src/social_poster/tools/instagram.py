"""Instagram posting tool via the Instagram Graph API.

Instagram requires a publicly reachable image URL. In production, upload the
hero image to your CDN/object store first and pass that URL as `image_path`
(an http(s) URL). Local file paths only work in DRY_RUN mode.
"""

from __future__ import annotations

from langchain_core.tools import tool

from ..config import settings
from ._publish import require, write_to_outbox


@tool
def post_to_instagram(caption: str, image_path: str | None = None) -> str:
    """Publish an image post to Instagram. Requires human approval first.

    Args:
        caption: Final caption including hashtags (within 2200 characters).
        image_path: In DRY_RUN, a local PNG path. In production, a public
            https URL to the hero image.

    Returns:
        A human-readable status string containing the media permalink.
    """
    if settings.dry_run:
        url = write_to_outbox("instagram", caption, image_path)
        return f"[DRY RUN] Instagram post staged in ./outbox -> {url}"

    import requests

    user_id = require(settings.instagram_user_id, "INSTAGRAM_USER_ID")
    token = require(settings.instagram_access_token, "INSTAGRAM_ACCESS_TOKEN")
    if not (image_path and image_path.startswith("http")):
        raise RuntimeError(
            "Instagram requires a public https image URL. Upload the hero image "
            "to a CDN and pass that URL as image_path."
        )

    base = "https://graph.facebook.com/v21.0"
    create = requests.post(
        f"{base}/{user_id}/media",
        data={"image_url": image_path, "caption": caption, "access_token": token},
        timeout=60,
    )
    create.raise_for_status()
    container_id = create.json()["id"]

    publish = requests.post(
        f"{base}/{user_id}/media_publish",
        data={"creation_id": container_id, "access_token": token},
        timeout=60,
    )
    publish.raise_for_status()
    media_id = publish.json()["id"]
    return f"Published to Instagram -> media id {media_id}"

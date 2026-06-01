"""LinkedIn posting tool via the UGC Posts REST API."""

from __future__ import annotations

from langchain_core.tools import tool

from ..config import settings
from ._publish import ensure_image, require, write_to_outbox


@tool
def post_to_linkedin(caption: str, image_path: str | None = None) -> str:
    """Publish a post to LinkedIn. Requires human approval first.

    Args:
        caption: Final post text (within 3000 characters).
        image_path: Optional local path to a hero image to upload and attach.

    Returns:
        A human-readable status string containing the post URN/permalink.
    """
    if settings.dry_run:
        url = write_to_outbox("linkedin", caption, image_path)
        return f"[DRY RUN] LinkedIn post staged in ./outbox -> {url}"

    import requests

    token = require(settings.linkedin_access_token, "LINKEDIN_ACCESS_TOKEN")
    author = require(settings.linkedin_author_urn, "LINKEDIN_AUTHOR_URN")  # e.g. urn:li:person:xxxx
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }

    media_assets = []
    if image_path:
        path = ensure_image(image_path)
        # 1) register an upload slot
        reg = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers=headers,
            json={
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": author,
                    "serviceRelationships": [
                        {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                    ],
                }
            },
            timeout=60,
        )
        reg.raise_for_status()
        value = reg.json()["value"]
        asset = value["asset"]
        upload_url = value["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        # 2) upload the bytes
        requests.put(
            upload_url,
            headers={"Authorization": f"Bearer {token}"},
            data=path.read_bytes(),
            timeout=120,
        ).raise_for_status()
        media_assets = [{"status": "READY", "media": asset}]

    share_media_category = "IMAGE" if media_assets else "NONE"
    body = {
        "author": author,
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": caption},
                "shareMediaCategory": share_media_category,
                **({"media": media_assets} if media_assets else {}),
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }
    resp = requests.post(
        "https://api.linkedin.com/v2/ugcPosts", headers=headers, json=body, timeout=60
    )
    resp.raise_for_status()
    post_urn = resp.headers.get("x-restli-id") or resp.json().get("id", "")
    return f"Published to LinkedIn -> {post_urn}"

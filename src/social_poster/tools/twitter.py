"""Twitter / X posting tool (v2 API, optional media upload via v1.1)."""

from __future__ import annotations

from langchain_core.tools import tool

from ..config import settings
from ._publish import ensure_image, require, write_to_outbox


@tool
def post_to_twitter(caption: str, image_path: str | None = None) -> str:
    """Publish a post (tweet) to Twitter/X. Requires human approval first.

    Args:
        caption: Final tweet text, already within the 280 character limit.
        image_path: Optional path to a hero image to attach.

    Returns:
        A human-readable status string containing the post permalink.
    """
    if settings.dry_run:
        url = write_to_outbox("twitter", caption, image_path)
        return f"[DRY RUN] Tweet staged in ./outbox -> {url}"

    import tweepy

    client = tweepy.Client(
        bearer_token=settings.twitter_bearer_token,
        consumer_key=require(settings.twitter_api_key, "TWITTER_API_KEY"),
        consumer_secret=require(settings.twitter_api_secret, "TWITTER_API_SECRET"),
        access_token=require(settings.twitter_access_token, "TWITTER_ACCESS_TOKEN"),
        access_token_secret=require(settings.twitter_access_secret, "TWITTER_ACCESS_SECRET"),
    )

    media_ids = None
    if image_path:
        path = ensure_image(image_path)
        auth = tweepy.OAuth1UserHandler(
            settings.twitter_api_key,
            settings.twitter_api_secret,
            settings.twitter_access_token,
            settings.twitter_access_secret,
        )
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(str(path))
        media_ids = [media.media_id]

    resp = client.create_tweet(text=caption, media_ids=media_ids)
    tweet_id = resp.data["id"]
    return f"Published to Twitter/X -> https://x.com/i/web/status/{tweet_id}"

"""Image generation tool with a provider-agnostic backend.

Resolution order (configurable via SOCIAL_POSTER_IMAGE_PROVIDER):
  openai      -> DALL-E / gpt-image-1 via the OpenAI SDK
  gemini      -> Imagen via google-genai
  placeholder -> a locally rendered branded gradient card (no network, no keys)

Every backend returns a path to a PNG saved under ./assets so the UI can show
it and the posting tools can upload it.
"""

from __future__ import annotations

import hashlib
import textwrap
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool

from ..config import ASSETS_DIR, settings


def _slug(prompt: str) -> str:
    digest = hashlib.sha1(prompt.encode()).hexdigest()[:8]
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"hero-{stamp}-{digest}.png"


def _render_placeholder(prompt: str, path: Path) -> None:
    """Render a clean branded gradient card with the prompt wrapped on top.

    Uses only Pillow + numpy so it works with zero credentials.
    """
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    w, h = 1024, 1024
    # Diagonal gradient between two brand colors.
    top = np.array([99, 102, 241])  # indigo
    bottom = np.array([236, 72, 153])  # pink
    ramp = np.linspace(0, 1, h)[:, None]
    grad = (top[None, :] * (1 - ramp) + bottom[None, :] * ramp).astype("uint8")
    arr = np.repeat(grad[:, None, :], w, axis=1)
    img = Image.fromarray(arr, "RGB")

    img = img.convert("RGBA")

    def _font(size: int):
        for candidate in (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ):
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    # Translucent panel for legibility (composited so alpha is honored).
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    odraw.rounded_rectangle([64, 360, 960, 760], radius=32, fill=(15, 15, 35, 140))
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    draw.text((96, 96), "PostPilot", font=_font(64), fill="white")
    draw.text((96, 184), "AI-generated hero image", font=_font(30), fill=(235, 235, 255))

    wrapped = textwrap.fill(prompt.strip(), width=30)
    draw.multiline_text((96, 408), wrapped, font=_font(46), fill="white", spacing=14)
    img.convert("RGB").save(path)


def _render_openai(prompt: str, path: Path) -> None:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    result = client.images.generate(model="gpt-image-1", prompt=prompt, size="1024x1024")
    import base64

    path.write_bytes(base64.b64decode(result.data[0].b64_json))


def _render_gemini(prompt: str, path: Path) -> None:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    resp = client.models.generate_images(
        model="imagen-4.0-generate-001", prompt=prompt, config={"number_of_images": 1}
    )
    path.write_bytes(resp.generated_images[0].image.image_bytes)


@tool
def generate_image(prompt: str) -> str:
    """Generate a hero image for the campaign from a vivid visual prompt.

    Args:
        prompt: A concrete, descriptive image prompt (subject, style, mood,
            colors). Avoid text-in-image requests.

    Returns:
        The local file path of the saved PNG. Pass this path to the posting
        tools and reference it when presenting drafts to the user.
    """
    path = ASSETS_DIR / _slug(prompt)
    provider = settings.resolved_image_provider()
    try:
        if provider == "openai":
            _render_openai(prompt, path)
        elif provider == "gemini":
            _render_gemini(prompt, path)
        else:
            _render_placeholder(prompt, path)
    except Exception as exc:  # pragma: no cover - network/credential failures
        # Never let image generation break the agentic flow: fall back locally.
        _render_placeholder(f"{prompt}\n\n[fallback: {exc}]", path)
        provider = "placeholder"
    return str(path)

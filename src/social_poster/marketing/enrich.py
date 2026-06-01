"""Crawl a website *you own* to build the business profile.

Scope guardrails:
  * Same-domain only, a small page budget, polite delays, robots.txt honored.
  * Intended for YOUR OWN site (the one whose business this CRM serves) to
    auto-fill `business_profile.yaml` and surface your company's own public
    contact addresses (info@, sales@). It is not a third-party lead scraper.

If an LLM is configured it summarizes the site into a clean profile; otherwise
it falls back to title/meta/heading extraction so it still works offline.
"""

from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_HEADERS = {"User-Agent": "PostPilot-DealDesk/1.0 (+own-site profile builder)"}
_CANDIDATE_PATHS = ("", "/about", "/about-us", "/company", "/services", "/products", "/contact")


def _same_domain(base: str, url: str) -> bool:
    return urlparse(base).netloc == urlparse(url).netloc


def _robots_ok(base: str, url: str) -> bool:
    try:
        rp = RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        rp.read()
        return rp.can_fetch(_HEADERS["User-Agent"], url)
    except Exception:
        return True  # if robots can't be read, default to allowed for own site


def fetch_page(url: str, timeout: int = 20) -> tuple[str, str, set[str]]:
    """Return (title, visible_text, emails) for a single page."""
    resp = requests.get(url, headers=_HEADERS, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = (soup.title.string if soup.title and soup.title.string else "").strip()
    meta = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta.get("content", "").strip() if meta else ""
    text = " ".join(soup.get_text(separator=" ").split())
    emails = set(_EMAIL_RE.findall(resp.text))
    # surface mailto links too
    for a in soup.select("a[href^=mailto]"):
        emails.add(a["href"].split(":", 1)[1].split("?")[0])
    return title, (meta_desc + "\n" + text).strip(), emails


def crawl_site(base_url: str, *, max_pages: int = 6, delay: float = 1.0) -> dict:
    """Politely crawl a handful of same-domain pages. Returns aggregated text."""
    if not base_url.startswith("http"):
        base_url = "https://" + base_url
    pages: list[dict] = []
    emails: set[str] = set()
    seen: set[str] = set()
    title = ""

    for path in _CANDIDATE_PATHS:
        if len(pages) >= max_pages:
            break
        url = urljoin(base_url, path)
        if url in seen:
            continue
        seen.add(url)
        if not _same_domain(base_url, url) or not _robots_ok(base_url, url):
            continue
        try:
            t, text, found = fetch_page(url)
        except Exception:
            continue
        title = title or t
        emails |= found
        pages.append({"url": url, "title": t, "text": text[:4000]})
        time.sleep(delay)

    # keep only emails on the site's own domain (the company's own addresses)
    domain = urlparse(base_url).netloc.replace("www.", "")
    own_emails = sorted(e for e in emails if e.lower().endswith(domain.lower()))
    return {"base_url": base_url, "title": title, "pages": pages,
            "company_emails": own_emails, "domain": domain}


def build_profile_from_site(base_url: str, *, model: str | None = None) -> dict:
    """Crawl the site and synthesize business-profile fields.

    Uses the LLM when available; otherwise returns a sensible extraction-only
    profile so it still runs offline.
    """
    data = crawl_site(base_url)
    corpus = "\n\n".join(f"# {p['title']}\n{p['text']}" for p in data["pages"])[:12000]

    profile = {
        "name": data["title"].split("|")[0].split("-")[0].strip() or data["domain"],
        "website": data["base_url"],
        "description": data["pages"][0]["text"][:400] if data["pages"] else "",
    }
    if data["company_emails"]:
        profile["contact_email"] = data["company_emails"][0]

    if not corpus:
        return {"profile": profile, "company_emails": data["company_emails"],
                "note": "No readable content fetched; profile is minimal."}

    try:
        from langchain.chat_models import init_chat_model
        from ..config import settings

        llm = init_chat_model(model or settings.model)
        prompt = (
            "From this company's own website content, produce a concise JSON object "
            "with keys: name, one_liner, description, products (list), value_props (list), "
            "ideal_customer, target_industries (list), tone, cta. Base it ONLY on the "
            "content provided; do not invent. Content:\n\n" + corpus
        )
        resp = llm.invoke(prompt)
        import json as _json

        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            llm_profile = _json.loads(match.group(0))
            llm_profile.update({k: v for k, v in profile.items() if v})
            profile = llm_profile
    except Exception as exc:  # offline / no key / parse error -> keep extraction
        profile["note"] = f"LLM enrichment skipped: {exc}"

    return {"profile": profile, "company_emails": data["company_emails"]}

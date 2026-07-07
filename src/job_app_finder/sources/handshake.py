"""Handshake best-effort adapter — authenticated, school-gated, single-user.

Off by default: only runs if "handshake" is listed under `besteffort_enabled`
in config.yaml AND `HANDSHAKE_COOKIE` is set in .env. Uses a cookie captured
from an authenticated browser session (copy the `Cookie:` request header from
DevTools on app.joinhandshake.com after logging in) rather than a Playwright
login flow, since login UIs vary by school SSO and change often.

CSS selectors below are best-effort placeholders — Handshake's DOM is not
public/stable, so this adapter is the most likely to need hand-adjustment
against the real site before it returns anything. Verify selectors in
DevTools before enabling. Rate-limited to one request every few seconds;
never raise on scrape failure (best-effort, single-user, low-rate per the
project's compliance stance).
"""

import asyncio
from datetime import datetime, timezone
from urllib.parse import quote

from job_app_finder.config import get_env
from job_app_finder.models import Anchor, Posting
from job_app_finder.sources.base import AdapterMeta, SourceAdapter, register

SEARCH_URL = "https://app.joinhandshake.com/stu/postings"
COOKIE_DOMAIN = "app.joinhandshake.com"
RATE_LIMIT_SECONDS = 3.0
PAGE_TIMEOUT_MS = 10_000


def parse_cookie_header(cookie_header: str, domain: str = COOKIE_DOMAIN) -> list[dict]:
    """Parse a raw `Cookie:` header value into Playwright's add_cookies() shape."""
    cookies = []
    for part in cookie_header.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        cookies.append({"name": name.strip(), "value": value.strip(), "domain": domain, "path": "/"})
    return cookies


async def _extract_posting(card, fetched_at: str) -> Posting | None:
    try:
        posting_id = await card.get_attribute("data-posting-id")
        title_el = await card.query_selector("[data-hook='posting-title']")
        company_el = await card.query_selector("[data-hook='posting-employer-name']")
        location_el = await card.query_selector("[data-hook='posting-location']")
        link_el = await card.query_selector("a")

        title = (await title_el.inner_text()).strip() if title_el else None
        company = (await company_el.inner_text()).strip() if company_el else None
        location = (await location_el.inner_text()).strip() if location_el else None
        href = await link_el.get_attribute("href") if link_el else None

        if not (posting_id and title and company and href):
            return None

        url = href if href.startswith("http") else f"https://app.joinhandshake.com{href}"
        return Posting(
            source="handshake",
            external_id=posting_id,
            title=title,
            company=company,
            location_raw=location,
            lat=None,
            lon=None,
            is_remote="remote" in (location or "").lower(),
            url=url,
            description=None,
            posted_at=None,
            fetched_at=fetched_at,
        )
    except Exception:
        return None


class HandshakeAdapter(SourceAdapter):
    meta = AdapterMeta(name="handshake", kind="besteffort", priority=1, requires_auth=True, tos_risk="high")

    async def fetch(self, queries: list[str], anchors: list[Anchor]) -> list[Posting]:
        cookie_header = get_env("HANDSHAKE_COOKIE")
        if not cookie_header:
            return []
        try:
            from playwright.async_api import async_playwright  # optional `scrape` extra
        except ImportError:
            return []

        fetched_at = datetime.now(timezone.utc).isoformat()
        postings: list[Posting] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context()
                await context.add_cookies(parse_cookie_header(cookie_header))
                page = await context.new_page()
                for query in queries:
                    try:
                        await page.goto(f"{SEARCH_URL}?query={quote(query)}")
                        await page.wait_for_selector("[data-hook='posting-card']", timeout=PAGE_TIMEOUT_MS)
                        cards = await page.query_selector_all("[data-hook='posting-card']")
                        for card in cards:
                            posting = await _extract_posting(card, fetched_at)
                            if posting:
                                postings.append(posting)
                    except Exception:
                        continue  # best-effort — one bad query shouldn't sink the run
                    await asyncio.sleep(RATE_LIMIT_SECONDS)
            finally:
                await browser.close()

        return postings


register(HandshakeAdapter())

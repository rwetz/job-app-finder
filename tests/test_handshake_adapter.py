import asyncio

from job_app_finder.models import Anchor
from job_app_finder.sources.handshake import HandshakeAdapter, parse_cookie_header

FARGO = Anchor(name="Fargo, ND", zip="58102", lat=46.8772, lon=-96.7898)


def test_parse_cookie_header_splits_name_value_pairs():
    cookies = parse_cookie_header("session=abc123; other=xyz", domain="app.joinhandshake.com")
    assert {"name": "session", "value": "abc123", "domain": "app.joinhandshake.com", "path": "/"} in cookies
    assert {"name": "other", "value": "xyz", "domain": "app.joinhandshake.com", "path": "/"} in cookies


def test_parse_cookie_header_skips_malformed_segments():
    cookies = parse_cookie_header("session=abc123; ; malformed", domain="example.com")
    assert len(cookies) == 1
    assert cookies[0]["name"] == "session"


def test_fetch_returns_empty_without_cookie_env(monkeypatch):
    monkeypatch.delenv("HANDSHAKE_COOKIE", raising=False)
    adapter = HandshakeAdapter()
    assert asyncio.run(adapter.fetch(["intern"], [FARGO])) == []


def test_fetch_returns_empty_without_playwright_installed(monkeypatch):
    monkeypatch.setenv("HANDSHAKE_COOKIE", "session=abc123")
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "playwright.async_api" or name.startswith("playwright"):
            raise ImportError("no playwright in test env")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    adapter = HandshakeAdapter()
    assert asyncio.run(adapter.fetch(["intern"], [FARGO])) == []

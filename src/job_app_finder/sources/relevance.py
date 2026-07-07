"""Shared tech/CS/AI-ML relevance filter for boards whose own search is loose
or nonexistent (RemoteOK has no real full-text search; Remotive's search
still lets non-tech roles through). Used as a client-side gate, not a
replacement for each board's own query scoping.

Checked against the job TITLE only, as a whole-word/phrase match — not the
description. Company boilerplate in descriptions ("partner with our
engineering team") let non-tech roles like HR/PM/marketing slip through when
matched against free text; titles are a much more reliable signal.
"""

import re

TITLE_SIGNALS = [
    "engineer", "engineering", "developer", "dev", "programmer", "coder",
    "software", "backend", "front-end", "frontend", "back-end", "full-stack", "fullstack",
    "software development", "web development", "app development",
    "devops", "sre", "architect", "sdet",
    "data scientist", "data engineer", "machine learning", "ai engineer", "ml engineer",
    "artificial intelligence", "ai", "ml",
    "qa engineer", "test engineer", "quality engineer",
    "mobile developer", "ios developer", "android developer",
    "security engineer", "cloud engineer", "platform engineer", "infrastructure engineer",
    "systems engineer", "network engineer", "site reliability",
]


def _normalize(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def is_tech_relevant(title: str | None) -> bool:
    if not title:
        return False
    padded = f" {_normalize(title)} "
    return any(f" {signal} " in padded for signal in TITLE_SIGNALS)

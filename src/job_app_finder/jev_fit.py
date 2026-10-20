"""Posting-fit decision contract for TypeSafe Jev (shadow mode only).

Replaces the "ask a generative model why this posting matches" step with three
bounded judgments over one state. Nothing here writes to the postings table or
changes ranking: `decide()` returns a Decision that the caller may log as a
receipt. Human boundary: Jev never dismisses, applies to, or hides a posting.

Forbidden data in `state`: contact details, addresses, API keys, .env values.
Send a skills/level summary of the resume, not the resume file.
"""

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"

QUESTIONS: dict = {
    "level_fit": {
        "type": "choice",
        "instructions": "How does the seniority this posting asks for compare with the candidate's level?",
        "criteria": {
            "match": "Intern, new-grad or entry-level role the candidate can plausibly land",
            "stretch": "Asks for a little more experience than the candidate has, but not disqualifying",
            "too_senior": "Requires several years of experience or a senior/staff/lead title",
        },
    },
    "skills_fit": {
        "type": "score",
        "instructions": "How much of the posting's core technical work uses skills listed in the candidate summary?",
        "criteria": [
            "Almost none of the core work uses the candidate's skills",
            "Some overlap, but the core stack is different",
            "The core stack largely matches the candidate's skills",
            "Direct match on the core stack and the kind of work",
        ],
    },
    "hard_blocker": {
        "type": "noul",
        "instructions": "Does the posting state a hard requirement a student intern cannot meet, such as a security clearance, a completed advanced degree, or many years of experience?",
        "criteria": {
            "true": "An explicit, non-negotiable requirement the candidate lacks",
            "false": "No such requirement stated",
        },
    },
}

BLOCKER_SKIP_AT = 0.85   # above this: rank last, flag for human glance
LOW_CONFIDENCE = 0.60    # choice/score confidence below this: route to review
SHORTLIST_SCORE = 2.0    # skills_fit at or above this earns the Claude rationale


@dataclass
class Decision:
    route: str                      # "shortlist" | "rank" | "deprioritize" | "review"
    fit: float | None               # 0..1 composite for sorting; None when routed to review
    answers: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)


def build_request(resume_summary: str, title: str, company: str, description: str | None) -> dict:
    return {
        "model": MODEL,
        "state": {
            "candidate": resume_summary,
            "posting": {"title": title, "company": company, "description": description or ""},
        },
        "questions": QUESTIONS,
    }


def decide(response: dict) -> Decision:
    """Turn a /v1/systemone response into a routing decision. Pure; no I/O."""
    a = response["answers"]
    level, skills, blocker = a["level_fit"], a["skills_fit"], a["hard_blocker"]
    common = {"answers": a, "usage": response.get("usage", {})}

    if blocker["noul"] >= BLOCKER_SKIP_AT or level["choice"] == "too_senior":
        return Decision("deprioritize", 0.0, **common)
    if min(level["confidence"], skills["confidence"]) < LOW_CONFIDENCE:
        return Decision("review", None, **common)

    fit = skills["score"] / (len(skills["legend"]) - 1)
    if level["choice"] == "stretch":
        fit *= 0.7
    route = "shortlist" if skills["score"] >= SHORTLIST_SCORE and level["choice"] == "match" else "rank"
    return Decision(route, round(fit, 3), **common)


def judge(resume_summary: str, title: str, company: str, description: str | None) -> dict:
    """Live call. Requires TYPESAFE_API_KEY in the environment. Not wired into ingest."""
    key = os.environ["TYPESAFE_API_KEY"]
    body = json.dumps(build_request(resume_summary, title, company, description)).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as r:
        out = json.load(r)
    out["_latency_s"] = round(time.perf_counter() - t0, 3)
    return out

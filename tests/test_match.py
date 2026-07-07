from pathlib import Path

from job_app_finder.db.database import init_db
from job_app_finder.db.postings_repo import upsert_postings
from job_app_finder.match import (
    claude_rationale_shortlist,
    compute_match_score,
    keyword_score,
    score_all_postings,
)
from job_app_finder.models import Posting

RESUME = "Experienced in Python, SQL, and distributed systems. Software engineering intern seeking backend roles."


def test_keyword_score_higher_for_relevant_posting():
    relevant = keyword_score(RESUME, "Software Engineering Intern — Python backend team")
    irrelevant = keyword_score(RESUME, "Marketing Coordinator — social media campaigns")
    assert relevant > irrelevant


def test_keyword_score_zero_for_empty_inputs():
    assert keyword_score("", "anything") == 0.0
    assert keyword_score(RESUME, "") == 0.0


def test_compute_match_score_falls_back_to_keyword_only_without_sentence_transformers(monkeypatch):
    import job_app_finder.match as match_mod

    monkeypatch.setattr(match_mod, "embedding_score", lambda r, p: None)
    score = compute_match_score(RESUME, "Software Engineering Intern", "Python backend")
    assert score == keyword_score(RESUME, "Software Engineering Intern\nPython backend")


def test_score_all_postings_updates_null_scores_only(tmp_path: Path):
    conn = init_db(tmp_path / "t.db")
    upsert_postings(
        conn,
        [
            Posting(
                source="adzuna", external_id="1", title="Software Engineering Intern",
                company="Acme", location_raw="Fargo, ND", lat=46.8, lon=-96.8, is_remote=False,
                url="https://example.com/1", description="Python backend team",
                posted_at="2026-07-01T00:00:00Z", fetched_at="2026-07-07T00:00:00Z",
            )
        ],
    )
    updated = score_all_postings(conn, RESUME)
    assert updated == 1
    row = conn.execute("SELECT match_score FROM postings").fetchone()
    assert row["match_score"] is not None

    # second pass: score already set, nothing left to update
    assert score_all_postings(conn, RESUME) == 0


def test_claude_rationale_shortlist_noop_without_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    conn = init_db(tmp_path / "t.db")
    assert claude_rationale_shortlist(conn, RESUME, "claude-opus-4-8", 10) == 0

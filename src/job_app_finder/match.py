"""Match scoring: local embeddings + keyword overlap for bulk scoring (free),
optional Claude pass for a one-line rationale on the top-N shortlist only.
"""

import functools
import re
import sqlite3

from job_app_finder.config import get_env

_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z+#.]*")
_STOPWORDS = {
    "the", "and", "for", "are", "with", "you", "your", "our", "will", "have",
    "this", "that", "from", "who", "can", "all", "not", "but", "org", "com",
}


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2} - _STOPWORDS


def keyword_score(resume_text: str, posting_text: str) -> float:
    resume_tokens = _tokenize(resume_text)
    posting_tokens = _tokenize(posting_text)
    if not resume_tokens or not posting_tokens:
        return 0.0
    overlap = resume_tokens & posting_tokens
    return len(overlap) / len(resume_tokens)


@functools.lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer  # optional `match` extra

    return SentenceTransformer("all-MiniLM-L6-v2")


def embedding_score(resume_text: str, posting_text: str) -> float | None:
    try:
        model = _embedding_model()
    except ImportError:
        return None
    from sentence_transformers import util

    resume_vec = model.encode(resume_text, convert_to_tensor=True)
    posting_vec = model.encode(posting_text, convert_to_tensor=True)
    cos_sim = util.cos_sim(resume_vec, posting_vec).item()
    return max(0.0, min(1.0, (cos_sim + 1) / 2))


def compute_match_score(resume_text: str, title: str, description: str | None) -> float:
    posting_text = f"{title}\n{description or ''}"
    kw = keyword_score(resume_text, posting_text)
    emb = embedding_score(resume_text, posting_text)
    if emb is None:
        return kw
    return 0.6 * emb + 0.4 * kw


def score_all_postings(conn: sqlite3.Connection, resume_text: str) -> int:
    rows = conn.execute(
        "SELECT id, title, description FROM postings WHERE match_score IS NULL"
    ).fetchall()
    for row in rows:
        score = compute_match_score(resume_text, row["title"], row["description"])
        conn.execute("UPDATE postings SET match_score = ? WHERE id = ?", (score, row["id"]))
    conn.commit()
    return len(rows)


def _rationale_prompt(resume_text: str, title: str, company: str, description: str | None) -> str:
    return (
        f"Resume:\n{resume_text}\n\n"
        f"Job posting: {title} at {company}\n{description or ''}\n\n"
        "In one sentence, explain why this posting is or isn't a strong match for the resume."
    )


def claude_rationale_shortlist(
    conn: sqlite3.Connection, resume_text: str, model: str, top_n: int
) -> int:
    """Best-effort: one-line Claude rationale for the top-N unscored-rationale postings."""
    api_key = get_env("ANTHROPIC_API_KEY")
    if not api_key:
        return 0
    try:
        import anthropic
    except ImportError:
        return 0

    client = anthropic.Anthropic(api_key=api_key)
    rows = conn.execute(
        """
        SELECT id, title, company, description FROM postings
        WHERE match_rationale IS NULL AND match_score IS NOT NULL
        ORDER BY match_score DESC LIMIT ?
        """,
        (top_n,),
    ).fetchall()

    updated = 0
    for row in rows:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=200,
                output_config={"effort": "low"},
                messages=[
                    {
                        "role": "user",
                        "content": _rationale_prompt(
                            resume_text, row["title"], row["company"], row["description"]
                        ),
                    }
                ],
            )
            if response.stop_reason == "refusal":
                continue
            text = next((b.text for b in response.content if b.type == "text"), None)
            if not text:
                continue
        except Exception:
            continue

        conn.execute(
            "UPDATE postings SET match_rationale = ? WHERE id = ?", (text.strip(), row["id"])
        )
        updated += 1

    conn.commit()
    return updated

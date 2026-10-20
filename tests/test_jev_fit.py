"""Offline tests for the Jev posting-fit contract.

The responses below are hand-written to the documented /v1/systemone shape.
They prove routing logic and request construction only; they are NOT evidence
that Jev returns these answers. See scripts/jev_shadow.py for the live check.
"""

from job_app_finder.jev_fit import QUESTIONS, build_request, decide

LEGEND = {"0": "a", "1": "b", "2": "c", "3": "d"}


def _resp(level, level_conf, skills, skills_conf, blocker):
    return {
        "model": "jev-mock",
        "answers": {
            "level_fit": {"type": "choice", "choice": level, "confidence": level_conf, "probabilities": {}},
            "skills_fit": {"type": "score", "score": skills, "legend": LEGEND, "confidence": skills_conf, "probabilities": {}},
            "hard_blocker": {"type": "noul", "noul": blocker},
        },
        "usage": {"input_tokens": 300, "output_tokens": 30},
    }


def test_request_has_all_questions_and_no_extra_state():
    req = build_request("Python, SQL", "SWE Intern", "Acme", None)
    assert set(req["questions"]) == set(QUESTIONS)
    assert set(req["state"]) == {"candidate", "posting"}
    assert req["state"]["posting"]["description"] == ""


def test_obvious_match_is_shortlisted():
    d = decide(_resp("match", 0.9, 2.8, 0.9, 0.02))
    assert d.route == "shortlist" and d.fit > 0.9


def test_ambiguous_low_confidence_goes_to_review_not_ranked():
    d = decide(_resp("stretch", 0.4, 1.5, 0.5, 0.3))
    assert d.route == "review" and d.fit is None


def test_hard_blocker_is_deprioritized_never_dropped():
    d = decide(_resp("match", 0.9, 3.0, 0.9, 0.95))
    assert d.route == "deprioritize" and d.fit == 0.0


def test_too_senior_is_deprioritized():
    assert decide(_resp("too_senior", 0.9, 3.0, 0.9, 0.1)).route == "deprioritize"


def test_stretch_is_discounted_and_not_shortlisted():
    d = decide(_resp("stretch", 0.9, 2.5, 0.9, 0.1))
    assert d.route == "rank" and d.fit < 0.7

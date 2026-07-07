from job_app_finder.sources.relevance import is_tech_relevant


def test_is_tech_relevant_true_for_software_role():
    assert is_tech_relevant("Software Engineer")


def test_is_tech_relevant_true_for_ai_ml_role():
    assert is_tech_relevant("Machine Learning Researcher")
    assert is_tech_relevant("Senior AI Engineer")


def test_is_tech_relevant_false_for_non_tech_role():
    assert not is_tech_relevant("Social Media Coordinator")
    assert not is_tech_relevant("Senior Product Manager")
    assert not is_tech_relevant("Human Resources Generalist")
    assert not is_tech_relevant("Business Development Executive")
    assert not is_tech_relevant("Sales Development Representative")


def test_is_tech_relevant_true_for_development_phrases():
    assert is_tech_relevant("Software Development Engineer")
    assert is_tech_relevant("Web Development Intern")


def test_is_tech_relevant_false_for_none_or_empty():
    assert not is_tech_relevant(None)
    assert not is_tech_relevant("")


def test_is_tech_relevant_does_not_match_substring_inside_other_words():
    # "ai" / "ml" / "dev" must not match inside unrelated words.
    assert not is_tech_relevant("Chair of the Committee")
    assert not is_tech_relevant("HTML Email Designer")
    assert not is_tech_relevant("Devotions Coordinator")

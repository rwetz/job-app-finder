from job_app_finder.dedup import canonicalize_url, fuzzy_key


def test_canonicalize_url_strips_tracking_params_and_trailing_slash():
    a = canonicalize_url("https://Example.com/jobs/123/?utm_source=x&ref=y")
    b = canonicalize_url("https://example.com/jobs/123")
    assert a == b


def test_canonicalize_url_keeps_meaningful_query_params():
    url = canonicalize_url("https://example.com/jobs?id=123")
    assert "id=123" in url


def test_fuzzy_key_ignores_case_and_punctuation():
    a = fuzzy_key("Acme, Inc.", "Software Engineer Intern", "Fargo, ND")
    b = fuzzy_key("acme inc", "software engineer intern", "fargo nd")
    assert a == b


def test_fuzzy_key_differs_on_title():
    a = fuzzy_key("Acme", "Software Engineer Intern", "Fargo, ND")
    b = fuzzy_key("Acme", "Data Science Intern", "Fargo, ND")
    assert a != b

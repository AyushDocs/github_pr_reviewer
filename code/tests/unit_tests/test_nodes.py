from agent.nodes.summarize import _format_reviews


def test_format_reviews_parses_json():
    reviews = [
        {
            "file": "app/auth.py",
            "review": '{"severity":"HIGH","issue":"SQL Injection","explanation":"bad","suggested_fix":"fix it"}',
        },
    ]
    result = _format_reviews(reviews, "Code")
    assert "[Code]" in result
    assert "app/auth.py" in result
    assert "HIGH" in result
    assert "SQL Injection" in result


def test_format_reviews_falls_back_for_bad_json():
    reviews = [
        {"file": "app/auth.py", "review": "some raw text without json"},
    ]
    result = _format_reviews(reviews, "Code")
    assert "[Code]" in result
    assert "app/auth.py" in result
    assert "?" in result


def test_format_reviews_empty():
    assert _format_reviews([], "Code") == ""

from agent.evaluators.quality import evaluate_quality
from agent.evaluators.hallucination import detect_hallucinations


def test_quality_perfect_reviews():
    reviews = [
        {
            "file": "app/auth.py",
            "review": '{"severity":"HIGH","issue":"SQL Injection","explanation":"Direct string concatenation in query","suggested_fix":"Use parameterized queries"}',
        },
    ]
    result = evaluate_quality(reviews, [])
    assert result["score"] == 100.0
    assert result["issues"] == []


def test_quality_deducts_for_unparseable():
    reviews = [
        {"file": "app/auth.py", "review": "not json at all"},
        {
            "file": "app/config.py",
            "review": '{"severity":"HIGH","issue":"Hardcoded key","explanation":"Secret in source","suggested_fix":"Use env vars"}',
        },
    ]
    result = evaluate_quality(reviews, [])
    assert result["score"] < 100.0
    assert any("unparseable" in i for i in result["issues"])


def test_quality_deducts_for_vague():
    reviews = [
        {
            "file": "app/auth.py",
            "review": '{"severity":"??","issue":"Bad code","explanation":"","suggested_fix":""}',
        },
    ]
    result = evaluate_quality(reviews, [])
    assert result["score"] < 100.0


def test_hallucination_returns_empty_for_normal():
    diffs = [{"filename": "app/auth.py", "patch": "username = request.form['user']\nquery = f'SELECT * FROM users WHERE username={username}'"}]
    reviews = [
        {
            "file": "app/auth.py",
            "review": '{"severity":"HIGH","issue":"SQL Injection","explanation":"SQL injection in query","suggested_fix":"Use parameterized queries"}',
        },
    ]
    flags = detect_hallucinations(reviews, [], diffs)
    assert len(flags) == 0


def test_hallucination_flags_generic_false_positive():
    diffs = [{"filename": "app/hello.py", "patch": "print('hello world')"}]
    reviews = [
        {
            "file": "app/hello.py",
            "review": '{"severity":"HIGH","issue":"Potential SQL Injection","explanation":"Possible SQL injection risk","suggested_fix":"Use parameterized queries"}',
        },
    ]
    flags = detect_hallucinations(reviews, [], diffs)
    assert len(flags) == 1

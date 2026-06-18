from unittest.mock import patch, MagicMock

from agent.nodes.comment import _parse_review, _build_file_comment


def test_parse_review_valid():
    raw = '{"severity":"HIGH","issue":"SQL Injection","explanation":"Bad","suggested_fix":"Fix it"}'
    result = _parse_review(raw)
    assert result is not None
    assert result["severity"] == "HIGH"
    assert result["issue"] == "SQL Injection"


def test_parse_review_with_markdown_fence():
    raw = '```json\n{"severity":"LOW","issue":"Typo","explanation":"Minor","suggested_fix":"Fix"}\n```'
    result = _parse_review(raw)
    assert result is not None
    assert result["severity"] == "LOW"


def test_parse_review_invalid():
    assert _parse_review("not json") is None
    assert _parse_review("") is None
    assert _parse_review(None) is None


def test_build_file_comment_with_reviews():
    reviews = [
        {"file": "app.py", "review": '{"severity":"HIGH","issue":"SQLi","explanation":"Bad query","suggested_fix":"Use params"}'},
    ]
    security_reviews = [
        {"file": "app.py", "review": '{"severity":"CRITICAL","issue":"RCE","explanation":"exec() used","suggested_fix":"Remove"}'},
    ]
    body = _build_file_comment("app.py", reviews, security_reviews)
    assert "app.py" in body
    assert "HIGH" in body
    assert "SQLi" in body
    assert "CRITICAL" in body
    assert "RCE" in body


def test_build_file_comment_empty():
    body = _build_file_comment("app.py", [], [])
    assert "app.py" in body
    assert "**" not in body


def test_build_file_comment_skips_unparseable():
    reviews = [
        {"file": "app.py", "review": "garbage"},
    ]
    body = _build_file_comment("app.py", reviews, [])
    assert "garbage" not in body


def test_github_tool_get_pr_files():
    with patch("agent.tools.github_tool.gh") as mock_gh:
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_file = MagicMock()
        mock_file.filename = "app.py"
        mock_file.patch = "diff content"
        mock_file.status = "modified"
        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        mock_gh.get_repo.return_value = mock_repo

        from agent.tools.github_tool import get_pr_files
        result = get_pr_files("test/repo", 1)

    assert result["files"] == ["app.py"]
    assert len(result["diffs"]) == 1
    assert result["diffs"][0]["filename"] == "app.py"
    assert result["diffs"][0]["patch"] == "diff content"


def test_github_tool_skips_files_without_patch():
    with patch("agent.tools.github_tool.gh") as mock_gh:
        mock_repo = MagicMock()
        mock_pr = MagicMock()
        mock_file = MagicMock()
        mock_file.filename = "large.bin"
        mock_file.patch = None
        mock_file.status = "added"
        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr
        mock_gh.get_repo.return_value = mock_repo

        from agent.tools.github_tool import get_pr_files
        result = get_pr_files("test/repo", 1)

    assert result["files"] == ["large.bin"]
    assert result["diffs"] == []

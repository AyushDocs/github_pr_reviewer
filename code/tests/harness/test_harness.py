"""Pytest tests for the evaluation harness.

These test the harness logic (metric computation, parsing) without
making real API calls. The actual regression tests (run_full_* below)
will invoke the real LLM and are skipped by default.
"""

import os
os.environ.setdefault("AI_API_KEY", "test-key")
os.environ.setdefault("GITHUB_TOKEN", "test-token")

import json
from unittest.mock import patch, MagicMock
from tests.harness.test_cases import TEST_CASES, get_test_case
from tests.harness.runner import run_test_case, _parse_review


def test_parse_review_valid():
    raw = json.dumps({"severity": "HIGH", "issue": "Test", "explanation": "x", "suggested_fix": "y"})
    result = _parse_review(raw)
    assert result is not None
    assert result["severity"] == "HIGH"


def test_parse_review_with_markdown_fence():
    raw = "```json\n" + json.dumps({"severity": "LOW", "issue": "Test"}) + "\n```"
    result = _parse_review(raw)
    assert result is not None


def test_parse_review_invalid():
    assert _parse_review("not json") is None


def test_parse_review_empty():
    assert _parse_review("") is None
    assert _parse_review(None) is None


def test_test_cases_have_required_fields():
    for tc in TEST_CASES:
        assert "name" in tc
        assert "diffs" in tc
        assert "expected" in tc
        for diff in tc["diffs"]:
            assert "filename" in diff
            assert "patch" in diff
        for exp in tc["expected"]:
            assert "file" in exp
            assert "severity" in exp
            assert "issue_contains" in exp
            assert "type" in exp


def test_get_test_case_found():
    tc = get_test_case("sql_injection")
    assert tc is not None
    assert tc["name"] == "sql_injection"


def test_get_test_case_not_found():
    assert get_test_case("nonexistent") is None


def test_runner_metric_computation():
    tc = {
        "name": "test_metrics",
        "diffs": [{"filename": "app/main.py", "patch": "x = 1"}],
        "expected": [
            {"file": "app/main.py", "severity": "HIGH", "issue_contains": "test", "type": "review"},
        ],
    }

    with (
        patch("tests.harness.runner.review_chain") as mock_r,
        patch("tests.harness.runner.security_chain") as mock_s,
    ):
        mock_r.return_value = MagicMock(content=json.dumps({"severity": "HIGH", "issue": "test issue", "explanation": "x", "suggested_fix": "y"}))
        mock_s.return_value = MagicMock(content=json.dumps({"severity": "LOW", "issue": "something else", "explanation": "x", "suggested_fix": "y"}))

        result = run_test_case(tc)

    assert result["true_positives"] == 1
    assert result["false_positives"] == 1
    assert result["false_negatives"] == 0
    assert result["precision"] == 0.5
    assert result["recall"] == 1.0
    assert result["f1"] == round(2 * 0.5 * 1.0 / 1.5, 3)


def test_runner_empty_expected():
    tc = {
        "name": "test_empty",
        "diffs": [{"filename": "app/main.py", "patch": "x = 1"}],
        "expected": [],
    }

    with (
        patch("tests.harness.runner.review_chain") as mock_r,
        patch("tests.harness.runner.security_chain") as mock_s,
    ):
        mock_r.return_value = MagicMock(content=json.dumps({"severity": "HIGH", "issue": "something", "explanation": "x", "suggested_fix": "y"}))
        mock_s.return_value = MagicMock(content=json.dumps({"severity": "LOW", "issue": "other", "explanation": "x", "suggested_fix": "y"}))

        result = run_test_case(tc)

    assert result["true_positives"] == 0
    assert result["false_positives"] == 2
    assert result["false_negatives"] == 0
    assert result["precision"] == 0.0
    assert result["recall"] == 1.0
    assert result["f1"] == 0.0


def test_runner_no_findings():
    tc = {
        "name": "test_no_findings",
        "diffs": [{"filename": "app/main.py", "patch": "x = 1"}],
        "expected": [],
    }

    with (
        patch("tests.harness.runner.review_chain") as mock_r,
        patch("tests.harness.runner.security_chain") as mock_s,
    ):
        mock_r.return_value = MagicMock(content=json.dumps({"severity": "LOW", "issue": "minor style", "explanation": "x", "suggested_fix": "y"}))
        mock_s.return_value = MagicMock(content=json.dumps({"severity": "LOW", "issue": "nits", "explanation": "x", "suggested_fix": "y"}))

        result = run_test_case(tc)

    assert result["true_positives"] == 0
    assert result["false_positives"] == 2
    assert result["false_negatives"] == 0
    assert result["precision"] == 0.0
    assert result["recall"] == 1.0
    assert result["f1"] == 0.0


def test_runner_handles_chain_exception():
    tc = {
        "name": "test_exception",
        "diffs": [{"filename": "app/main.py", "patch": "x = 1"}],
        "expected": [],
    }

    with (
        patch("tests.harness.runner.review_chain", side_effect=Exception("boom")),
        patch("tests.harness.runner.security_chain", side_effect=Exception("boom")),
    ):
        result = run_test_case(tc)

    assert result["findings"] == []
    assert result["true_positives"] == 0
    assert result["false_positives"] == 0

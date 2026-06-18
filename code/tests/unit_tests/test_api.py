import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

import os
os.environ["AI_API_KEY"] = "test-key"
os.environ["GITHUB_TOKEN"] = "test-token"
os.environ["AI_MODEL"] = "google/gemma-2-2b-it"
os.environ["LANGCHAIN_TRACING_V2"] = "false"

from api.main import app

client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_webhook_ignores_non_pr_events():
    payload = {"action": "created"}
    resp = client.post(
        "/webhook",
        json=payload,
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"


def test_webhook_ignores_closed_pr():
    payload = {
        "action": "closed",
        "repository": {"full_name": "test/repo"},
        "pull_request": {"number": 1},
    }
    resp = client.post(
        "/webhook",
        json=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ignored"


def test_webhook_rejects_bad_signature():
    with patch.dict(os.environ, {"WEBHOOK_SECRET": "mysecret"}):
        payload = {
            "action": "opened",
            "repository": {"full_name": "test/repo"},
            "pull_request": {"number": 1},
        }
        resp = client.post(
            "/webhook",
            json=payload,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Invalid signature"


def test_webhook_runs_review_on_pr_opened():
    mock_result = {
        "repo_name": "test/repo",
        "pr_number": 1,
        "quality_score": 85.0,
        "hallucination_flags": [],
    }

    with (
        patch("api.routes.app_auto.invoke", return_value=mock_result) as mock_invoke,
        patch.dict(os.environ, {"WEBHOOK_SECRET": ""}),
    ):
        payload = {
            "action": "opened",
            "repository": {"full_name": "test/repo"},
            "pull_request": {"number": 1},
        }
        resp = client.post(
            "/webhook",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["pr"] == 1
    assert data["quality_score"] == 85.0
    mock_invoke.assert_called_once_with({"repo_name": "test/repo", "pr_number": 1})


def test_webhook_handles_review_exception():
    with (
        patch("api.routes.app_auto.invoke", side_effect=Exception("LLM failed")) as mock_invoke,
        patch.dict(os.environ, {"WEBHOOK_SECRET": ""}),
    ):
        payload = {
            "action": "synchronize",
            "repository": {"full_name": "test/repo"},
            "pull_request": {"number": 2},
        }
        resp = client.post(
            "/webhook",
            json=payload,
            headers={"X-GitHub-Event": "pull_request"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert "LLM failed" in data["error"]
    mock_invoke.assert_called_once()

"""Tests for automated GitHub PR review (analyzer + routes wiring)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.pr_review.analyzer import PRAnalyzer, parse_ignore_patterns


def test_parse_ignore_patterns() -> None:
    p = parse_ignore_patterns("*.md, *.txt ,foo")
    assert "*.md" in p and "*.txt" in p and "foo" in p


def test_analyzer_python_detects_bare_except() -> None:
    async def _run() -> list:
        a = PRAnalyzer([])
        src = "try:\n    x()\nexcept:\n    pass\n"
        return await a.analyze_file("x.py", "", src)

    issues = asyncio.run(_run())
    severities = [i["severity"] for i in issues]
    assert "warning" in severities


def test_analyzer_should_ignore_globs() -> None:
    a = PRAnalyzer(["*.md", "yarn.lock"])
    assert a.should_ignore_file("README.md")
    assert a.should_ignore_file("pkg/yarn.lock")


def test_generate_summary_empty() -> None:
    async def _run() -> str:
        a = PRAnalyzer([])
        return await a.generate_summary([])

    s = asyncio.run(_run())
    assert "No issues" in s


def test_pr_review_webhook_disabled_by_default() -> None:
    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.post("/api/v1/pr-review/webhook", content=b"{}", headers={"X-GitHub-Event": "pull_request"})
    assert r.status_code == 503
    get_settings.cache_clear()


def test_pr_review_manual_disabled_by_default() -> None:
    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.post("/api/v1/pr-review/review/acme/core/1")
    assert r.status_code == 503
    get_settings.cache_clear()


def test_pr_review_webhook_rejects_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_PR_REVIEW_ENABLED", "true")
    monkeypatch.setenv("NEXA_PR_REVIEW_WEBHOOK_SECRET", "s3cret")
    get_settings.cache_clear()
    body = b"{}"
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pr-review/webhook",
            content=body,
            headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=deadbeef"},
        )
    assert r.status_code == 403
    get_settings.cache_clear()
    monkeypatch.delenv("NEXA_PR_REVIEW_ENABLED", raising=False)
    monkeypatch.delenv("NEXA_PR_REVIEW_WEBHOOK_SECRET", raising=False)


def test_pr_review_webhook_ignores_non_pr_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_PR_REVIEW_ENABLED", "true")
    get_settings.cache_clear()
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pr-review/webhook",
            content=b"{}",
            headers={"X-GitHub-Event": "issue"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ignored"
    get_settings.cache_clear()
    monkeypatch.delenv("NEXA_PR_REVIEW_ENABLED", raising=False)


def test_pr_review_webhook_triggers_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXA_PR_REVIEW_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.services.pr_review.orchestrator.PRReviewOrchestrator.review_pr",
        AsyncMock(
            return_value={"ok": True, "pr_number": 99, "action": "commented", "summary": "x"},
        ),
    )

    payload = {
        "action": "opened",
        "pull_request": {"number": 99},
        "repository": {"full_name": "acme/rocket"},
    }
    raw = json.dumps(payload).encode()
    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pr-review/webhook",
            content=raw,
            headers={"X-GitHub-Event": "pull_request", "Content-Type": "application/json"},
        )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "reviewed"
    assert data.get("result", {}).get("pr_number") == 99
    get_settings.cache_clear()
    monkeypatch.delenv("NEXA_PR_REVIEW_ENABLED", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


def test_pr_review_webhook_with_hmac_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_PR_REVIEW_ENABLED", "true")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_testtoken")
    monkeypatch.setenv("NEXA_PR_REVIEW_WEBHOOK_SECRET", "xyzzy")
    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.services.pr_review.orchestrator.PRReviewOrchestrator.review_pr",
        AsyncMock(return_value={"ok": True, "pr_number": 1, "action": "commented", "summary": ""}),
    )

    payload = {
        "action": "opened",
        "pull_request": {"number": 1},
        "repository": {"full_name": "o/r"},
    }
    raw = json.dumps(payload).encode()
    digest = hmac.new(b"xyzzy", raw, hashlib.sha256).hexdigest()

    with TestClient(app) as client:
        r = client.post(
            "/api/v1/pr-review/webhook",
            content=raw,
            headers={
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={digest}",
            },
        )
    assert r.status_code == 200
    get_settings.cache_clear()
    monkeypatch.delenv("NEXA_PR_REVIEW_ENABLED", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("NEXA_PR_REVIEW_WEBHOOK_SECRET", raising=False)

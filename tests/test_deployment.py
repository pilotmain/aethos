"""Tests for generic CLI deployment detector / executor."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.deployment.detector import DeploymentDetector, _normalize_provider
from app.services.deployment.executor import DeploymentExecutor
from app.services.host_executor_intent import parse_deploy_intent


def test_parse_deploy_intent_basic() -> None:
    assert parse_deploy_intent("deploy") == {"intent": "deploy", "provider": None, "raw_text": "deploy"}
    assert parse_deploy_intent("deploy this project") == {
        "intent": "deploy",
        "provider": None,
        "raw_text": "deploy this project",
    }
    assert parse_deploy_intent("deploy to vercel") == {
        "intent": "deploy",
        "provider": "vercel",
        "raw_text": "deploy to vercel",
    }
    assert parse_deploy_intent("push to production") is not None
    assert parse_deploy_intent("go live") is not None
    assert parse_deploy_intent("publish netlify")["provider"] == "netlify"


def test_normalize_provider() -> None:
    assert _normalize_provider("Google") == "gcloud"
    assert _normalize_provider("flyctl") == "fly"


def test_detector_skips_manual_only_in_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """AWS is manual_only — must not appear in automatic detection."""

    def _which(name: str) -> str | None:
        return "/usr/bin/" + name if name in {"aws", "vercel"} else None

    monkeypatch.setattr("app.services.deployment.detector.shutil.which", _which)
    avail = DeploymentDetector.detect_available()
    names = [c["name"] for c in avail]
    assert "aws" not in names
    assert "vercel" in names


def test_executor_aws_explicit_manual_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.deployment.executor.shutil.which", lambda _: "/usr/bin/aws")
    out = DeploymentExecutor.deploy_sync(str(Path.cwd()), provider="aws", timeout_seconds=5.0)
    assert out["success"] is False
    assert out["provider"] == "aws"
    assert "AWS" in (out.get("error") or "")


def test_executor_success_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    monkeypatch.setattr(
        "app.services.deployment.executor.DeploymentDetector.detect_by_file",
        lambda p: [],
    )
    monkeypatch.setattr(
        "app.services.deployment.executor.DeploymentDetector.detect_available",
        lambda: [
            {
                "name": "vercel",
                "binary": "vercel",
                "deploy_argv": ["vercel", "--prod"],
                "url_pattern": r"https://example\.vercel\.app",
            }
        ],
    )

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "Production: https://my-app.vercel.app\n"
    mock_proc.stderr = ""

    monkeypatch.setattr(
        "app.services.deployment.executor.subprocess.run",
        lambda *a, **k: mock_proc,
    )

    res = DeploymentExecutor.deploy_sync(str(root))
    assert res["success"] is True
    assert res["url"] == "https://my-app.vercel.app"

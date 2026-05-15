# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for generic CLI deployment detector / executor."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.deployment.detector import DeploymentDetector, _normalize_provider
from app.services.deployment.executor import DeploymentExecutor
from app.services.host_executor_intent import parse_deploy_intent


def test_parse_deploy_intent_basic() -> None:
    assert parse_deploy_intent("deploy") == {
        "intent": "deploy",
        "deploy_type": "deploy",
        "provider": None,
        "raw_text": "deploy",
    }
    assert parse_deploy_intent("deploy this project") == {
        "intent": "deploy",
        "deploy_type": "deploy",
        "provider": None,
        "raw_text": "deploy this project",
    }
    assert parse_deploy_intent("deploy to vercel") == {
        "intent": "deploy",
        "deploy_type": "deploy",
        "provider": "vercel",
        "raw_text": "deploy to vercel",
    }
    assert parse_deploy_intent("deploy railway to production") == {
        "intent": "deploy",
        "deploy_type": "deploy",
        "provider": "railway",
        "raw_text": "deploy railway to production",
    }
    assert parse_deploy_intent("preview deploy to netlify") == {
        "intent": "deploy",
        "deploy_type": "deploy_preview",
        "provider": "netlify",
        "raw_text": "preview deploy to netlify",
    }
    assert parse_deploy_intent("deploy preview")["deploy_type"] == "deploy_preview"
    assert parse_deploy_intent("push to production") is not None
    assert parse_deploy_intent("go live") is not None
    assert parse_deploy_intent("publish netlify")["provider"] == "netlify"
    assert parse_deploy_intent("restart an application on vercel.com") == {
        "intent": "deploy",
        "deploy_type": "deploy",
        "provider": "vercel",
        "raw_text": "restart an application on vercel.com",
    }
    assert parse_deploy_intent("redeploy my app on Vercel")["provider"] == "vercel"


def test_normalize_provider_extra() -> None:
    assert _normalize_provider("wrangler") == "cloudflare"
    assert _normalize_provider("pages") == "cloudflare"


def test_detector_skips_manual_only_in_available(monkeypatch: pytest.MonkeyPatch) -> None:
    def _which(name: str) -> str | None:
        return "/usr/bin/" + name if name in {"aws", "vercel"} else None

    monkeypatch.setattr("app.services.deployment.detector.shutil.which", _which)
    avail = DeploymentDetector.detect_available()
    names = [c["name"] for c in avail]
    assert "aws" not in names
    assert "vercel" in names


def test_detect_by_config_files_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "vercel.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        "app.services.deployment.detector.shutil.which",
        lambda name: "/x/vercel" if name == "vercel" else None,
    )
    got = DeploymentDetector.detect_by_config_files(str(tmp_path))
    assert any(x.get("name") == "vercel" for x in got)


def test_detect_by_framework_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pkg = {"dependencies": {"next": "^14.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(pkg), encoding="utf-8")

    monkeypatch.setattr(
        "app.services.deployment.detector.shutil.which",
        lambda name: "/v/vercel" if name == "vercel" else None,
    )
    got = DeploymentDetector.detect_by_framework(str(tmp_path))
    assert len(got) == 1 and got[0].get("name") == "vercel"


def test_executor_aws_explicit_manual_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.deployment.executor.shutil.which", lambda _: "/usr/bin/aws")
    out = DeploymentExecutor.deploy_sync(str(Path.cwd()), provider="aws", timeout_seconds=5.0)
    assert out["success"] is False
    assert out["provider"] == "aws"
    assert "AWS" in (out.get("error") or "")


def test_executor_auto_detect_off_explicit_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    monkeypatch.setattr(
        "app.services.deployment.executor.get_settings",
        lambda: type("S", (), {"nexa_deploy_auto_detect": False})(),
    )
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "ok https://x.vercel.app\n"
    mock_proc.stderr = ""
    monkeypatch.setattr("app.services.deployment.executor.shutil.which", lambda _: "/v/vercel")
    monkeypatch.setattr(
        "app.services.deployment.executor.subprocess.run",
        lambda *a, **k: mock_proc,
    )
    out = DeploymentExecutor.deploy_sync(str(root), provider="vercel", preview=False)
    assert out["success"] is True


def test_executor_auto_detect_off_bare_deploy_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    monkeypatch.setattr(
        "app.services.deployment.executor.get_settings",
        lambda: type("S", (), {"nexa_deploy_auto_detect": False})(),
    )
    out = DeploymentExecutor.deploy_sync(str(root), provider=None)
    assert out["success"] is False
    assert "Auto-detect is disabled" in (out.get("error") or "")


def test_executor_success_mock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()

    monkeypatch.setattr(
        "app.services.deployment.executor.DeploymentDetector.detect_by_file",
        lambda p: [],
    )
    monkeypatch.setattr(
        "app.services.deployment.executor.DeploymentDetector.detect_by_framework",
        lambda p: [],
    )
    monkeypatch.setattr(
        "app.services.deployment.executor.DeploymentDetector.detect_available",
        lambda *a, **k: [
            {
                "name": "vercel",
                "binary": "vercel",
                "deploy_argv": ["vercel", "--prod"],
                "url_pattern": r"https://[^\s\"']+\.vercel\.app[^\s\"']*",
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


def test_executor_preview_argv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    calls: list[object] = []

    def capture_run(cmd: object, **kwargs: object) -> MagicMock:
        calls.append(cmd)
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Preview: https://p.vercel.app\n"
        mock_proc.stderr = ""
        return mock_proc

    monkeypatch.setattr("app.services.deployment.executor.shutil.which", lambda _: "/v/vercel")
    monkeypatch.setattr("app.services.deployment.executor.subprocess.run", capture_run)

    DeploymentExecutor.deploy_sync(str(root), provider="vercel", preview=True)
    assert ["vercel", "--yes"] in calls


def test_extract_url_skips_localhost() -> None:
    from app.services.deployment.executor import DeploymentExecutor

    assert (
        DeploymentExecutor._extract_url("see http://localhost:3000 and https://x.vercel.app", None)
        == "https://x.vercel.app"
    )

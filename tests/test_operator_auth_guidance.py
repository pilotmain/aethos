# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operator CLI auth guidance (Vercel / gh not logged in)."""

from __future__ import annotations

import pytest

from app.services.operator_auth_guidance import (
    append_guidance_if_needed_github,
    append_guidance_if_needed_vercel,
    detect_github_auth_needed,
    detect_vercel_auth_needed,
    markdown_vercel_login_guidance,
)


def test_detect_vercel_auth_needed_from_stderr() -> None:
    assert detect_vercel_auth_needed(
        ok=False,
        stderr="Error: No existing credentials found. Please run `vercel login`",
        stdout="",
    )


def test_detect_vercel_skips_when_ok() -> None:
    assert not detect_vercel_auth_needed(ok=True, stderr="", stdout="user@x.com")


def test_detect_github_auth_needed() -> None:
    assert detect_github_auth_needed(
        ok=False,
        stderr="You are not logged in to any GitHub hosts.",
        stdout="",
        exit_code=1,
    )


def test_detect_github_skips_ok() -> None:
    assert not detect_github_auth_needed(
        ok=True,
        stderr="",
        stdout="Logged in to github.com as u",
        exit_code=0,
    )


def test_append_vercel_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_auth_guidance.auth_guidance_enabled",
        lambda: True,
    )
    whoami = {
        "ok": False,
        "stderr": "No existing credentials found.",
        "stdout": "",
    }
    out = append_guidance_if_needed_vercel("### Out\n", whoami)
    assert "Vercel authentication required" in out
    assert "vercel login" in out
    assert "docker exec -it" in out
    assert markdown_vercel_login_guidance() in out


def test_append_guidance_respects_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_auth_guidance.auth_guidance_enabled",
        lambda: False,
    )
    whoami = {"ok": False, "stderr": "No existing credentials found.", "stdout": ""}
    assert append_guidance_if_needed_vercel("BASE", whoami) == "BASE"


def test_append_github_guidance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_auth_guidance.auth_guidance_enabled",
        lambda: True,
    )
    auth = {
        "ok": False,
        "exit_code": 1,
        "stderr": "You are not logged in to github.com",
        "stdout": "",
    }
    out = append_guidance_if_needed_github("### gh\n", auth)
    assert "GitHub CLI authentication required" in out
    assert "gh auth login" in out

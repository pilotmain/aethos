"""Open-core extension loader + sandbox hook."""

from __future__ import annotations

import types

import pytest

from app.services.extensions import get_extension
from app.services.sandbox.runner import run_with_sandbox
from app.services.sandbox.types import SandboxMode


def test_get_extension_invalid_name() -> None:
    assert get_extension("../evil") is None
    assert get_extension("") is None


def test_run_with_sandbox_delegate(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = types.SimpleNamespace(
        run_in_sandbox=lambda mode, fn: ("delegated", mode, fn()),
    )

    def _ge(name: str):
        return fake if name == "sandbox" else None

    monkeypatch.setattr("app.services.sandbox.runner.get_extension", _ge)
    monkeypatch.setattr("app.services.sandbox.runner.has_pro_feature", lambda _fid: True)
    out = run_with_sandbox(SandboxMode.process, lambda: 7)
    assert out[0] == "delegated"
    assert out[2] == 7


def test_run_with_sandbox_fallback_without_package(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.sandbox.runner.get_extension", lambda n: None)
    assert run_with_sandbox(SandboxMode.process, lambda: 99) == 99


def test_run_with_sandbox_skips_extension_without_license(monkeypatch: pytest.MonkeyPatch) -> None:
    """Extension present but no Pro license → OSS in-process path."""
    fake = types.SimpleNamespace(
        run_in_sandbox=lambda mode, fn: "pro",
    )

    def _ge(name: str):
        return fake if name == "sandbox" else None

    monkeypatch.setattr("app.services.sandbox.runner.get_extension", _ge)
    monkeypatch.setattr("app.services.sandbox.runner.has_pro_feature", lambda _fid: False)
    assert run_with_sandbox(SandboxMode.process, lambda: 42) == 42

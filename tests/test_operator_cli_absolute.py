"""Optional absolute-path fallback for operator CLIs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


def test_apply_fallback_rewrites_when_setting_points_to_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = tmp_path / "vercel"
    fake.write_text("#!/bin/sh\necho ok\n")
    fake.chmod(0o755)
    s = SimpleNamespace(nexa_operator_cli_vercel_abs=str(fake), nexa_operator_cli_gh_abs="")
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)

    from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback

    out = apply_operator_cli_absolute_fallback(["vercel", "whoami"])
    assert out[0] == str(fake.resolve())
    assert out[1] == "whoami"


def test_apply_fallback_noop_when_setting_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        nexa_operator_cli_vercel_abs="",
        nexa_operator_cli_gh_abs="",
        nexa_operator_cli_git_abs="",
        nexa_operator_cli_railway_abs="",
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)

    from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback

    assert apply_operator_cli_absolute_fallback(["vercel", "whoami"]) == ["vercel", "whoami"]


def test_operator_cli_argv_resolves_absolute_executable(tmp_path: Path) -> None:
    fake = tmp_path / "gh"
    fake.write_text("#!/bin/sh\necho hi\n")
    fake.chmod(0o755)

    from app.services.operator_cli_absolute import operator_cli_argv_resolves

    assert operator_cli_argv_resolves([str(fake), "auth", "status"]) is True


def test_operator_cli_argv_resolves_false_for_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.operator_cli_absolute.which_operator_cli",
        lambda _name: None,
    )

    from app.services.operator_cli_absolute import operator_cli_argv_resolves

    missing = tmp_path / "nope"
    assert operator_cli_argv_resolves([str(missing), "x"]) is False

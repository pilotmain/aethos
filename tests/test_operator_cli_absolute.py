"""Optional absolute-path fallback for operator CLIs."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture(autouse=True)
def _reset_cli_registry() -> None:
    from app.services.cli_backends import reset_cli_backend_registry

    reset_cli_backend_registry()
    yield
    reset_cli_backend_registry()


def test_apply_fallback_rewrites_when_setting_points_to_executable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    for key in (
        "NEXA_OPERATOR_CLI_VERCEL_ABS",
        "NEXA_OPERATOR_CLI_GH_ABS",
        "NEXA_OPERATOR_CLI_GIT_ABS",
        "NEXA_OPERATOR_CLI_RAILWAY_ABS",
    ):
        monkeypatch.delenv(key, raising=False)
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
    monkeypatch.setattr("app.services.cli_backends.which_operator_cli", lambda *_a, **_kw: None)
    monkeypatch.setattr("app.services.cli_backends.shutil.which", lambda *_a, **_kw: None)
    for key in (
        "NEXA_OPERATOR_CLI_VERCEL_ABS",
        "NEXA_OPERATOR_CLI_GH_ABS",
        "NEXA_OPERATOR_CLI_GIT_ABS",
        "NEXA_OPERATOR_CLI_RAILWAY_ABS",
    ):
        monkeypatch.delenv(key, raising=False)
    s = SimpleNamespace(
        nexa_operator_cli_vercel_abs="",
        nexa_operator_cli_gh_abs="",
        nexa_operator_cli_git_abs="",
        nexa_operator_cli_railway_abs="",
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)

    from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback

    assert apply_operator_cli_absolute_fallback(["vercel", "whoami"]) == ["vercel", "whoami"]


def test_apply_fallback_prefers_os_environ_when_settings_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake = tmp_path / "vercel"
    fake.write_text("#!/bin/sh\necho ok\n")
    fake.chmod(0o755)
    monkeypatch.setenv("NEXA_OPERATOR_CLI_VERCEL_ABS", str(fake))
    s = SimpleNamespace(
        nexa_operator_cli_vercel_abs="",
        nexa_operator_cli_gh_abs="",
        nexa_operator_cli_git_abs="",
        nexa_operator_cli_railway_abs="",
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)

    from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback

    out = apply_operator_cli_absolute_fallback(["vercel", "whoami"])
    assert out[0] == str(fake.resolve())


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
    monkeypatch.setattr(
        "app.services.cli_backends.which_operator_cli",
        lambda _name: None,
    )
    monkeypatch.setattr(
        "app.services.cli_backends.shutil.which",
        lambda *_a, **_kw: None,
    )

    from app.services.operator_cli_absolute import operator_cli_argv_resolves

    missing = tmp_path / "nope"
    assert operator_cli_argv_resolves([str(missing), "x"]) is False

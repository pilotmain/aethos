"""CLI backend registry (explicit paths + PATH resolution)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.cli_backends import (
    CLIBackend,
    get_cli_command,
    register_cli_backend,
    reset_cli_backend_registry,
)


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_cli_backend_registry()
    yield
    reset_cli_backend_registry()


def test_get_cli_command_unknown_passes_through() -> None:
    assert get_cli_command("nonexistent_tool", ["--x"]) == ["nonexistent_tool", "--x"]


def test_get_cli_command_absolute_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "vercel"
    fake.write_text("#!/bin/sh\necho ok\n")
    fake.chmod(0o755)
    monkeypatch.setenv("NEXA_OPERATOR_CLI_VERCEL_ABS", str(fake))
    assert get_cli_command("vercel", ["whoami"]) == [str(fake.resolve()), "whoami"]


def test_cli_backend_resolve_absolute_executable(tmp_path: Path) -> None:
    p = tmp_path / "bin"
    p.mkdir()
    exe = p / "tool"
    exe.write_text("#!/bin/sh\necho\n")
    exe.chmod(0o755)
    b = CLIBackend(name="tool", command=str(exe))
    assert b.resolve_command() == str(exe.resolve())


def test_register_cli_backend_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = tmp_path / "v"
    fake.write_text("#!/bin/sh\necho\n")
    fake.chmod(0o755)
    register_cli_backend("vercel", str(fake))
    assert get_cli_command("vercel", ["whoami"])[0] == str(fake.resolve())


def test_settings_fallback_when_env_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
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
    s = SimpleNamespace(
        nexa_operator_cli_vercel_abs=str(fake),
        nexa_operator_cli_gh_abs="",
        nexa_operator_cli_git_abs="",
        nexa_operator_cli_railway_abs="",
    )
    monkeypatch.setattr("app.core.config.get_settings", lambda: s)
    assert get_cli_command("vercel", ["whoami"]) == [str(fake.resolve()), "whoami"]

"""Profile-shell CLI runner (login $SHELL + nvm/rc sources)."""

from __future__ import annotations

import os

import pytest

from app.services.operator_shell_cli import (
    resolve_login_shell_executable,
    run_allowlisted_argv_via_login_shell,
)


def test_rejects_disallowed_argv0() -> None:
    r = run_allowlisted_argv_via_login_shell(
        ["python", "-m", "pytest"],
        cwd=os.getcwd(),
        timeout=2.0,
        env=dict(os.environ),
    )
    assert r.get("error") == "argv_not_allowlisted"


def test_invokes_configured_login_shell_with_nvm_script(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict]] = []

    class Proc:
        returncode = 0
        stdout = "user@example.com"
        stderr = ""

    def fake_run(argv: list[str], **kw):  # noqa: ANN001
        calls.append((argv, kw))
        return Proc()

    monkeypatch.setattr("subprocess.run", fake_run)

    run_allowlisted_argv_via_login_shell(
        ["vercel", "whoami"],
        cwd="/tmp",
        timeout=30.0,
        env={"HOME": os.environ.get("HOME", "/tmp"), **os.environ},
    )
    assert calls
    argv0, kw = calls[0]
    shell = resolve_login_shell_executable()
    assert argv0[0] == shell
    assert argv0[1:3] == ["-l", "-c"]
    script = argv0[3]
    assert "nvm.sh" in script
    assert "bash_completion" in script
    assert "vercel" in script and "whoami" in script
    assert kw.get("env") is not None


def test_resolve_login_shell_prefers_shell_env(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    fake_sh = tmp_path / "myzsh"
    fake_sh.write_text("#!/bin/sh\necho\n")
    fake_sh.chmod(0o755)
    monkeypatch.setenv("SHELL", str(fake_sh))
    assert resolve_login_shell_executable() == str(fake_sh.resolve())

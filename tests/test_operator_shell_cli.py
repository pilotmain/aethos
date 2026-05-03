"""Profile-shell CLI runner (bash -lc + nvm/rc sources)."""

from __future__ import annotations

import os

import pytest

from app.services.operator_shell_cli import run_allowlisted_argv_via_login_shell


def test_rejects_disallowed_argv0() -> None:
    r = run_allowlisted_argv_via_login_shell(
        ["python", "-m", "pytest"],
        cwd=os.getcwd(),
        timeout=2.0,
        env=dict(os.environ),
    )
    assert r.get("error") == "argv_not_allowlisted"


def test_invokes_bash_with_nvm_script_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert argv0[:2] == ["/bin/bash", "-lc"]
    script = argv0[2]
    assert "nvm.sh" in script
    assert "vercel" in script and "whoami" in script
    assert kw.get("env") is not None


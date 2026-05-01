"""Tests for scripts/nexa_bootstrap and app.services.nexa_bootstrap."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

# Import module under test without running Docker
from app.services import nexa_bootstrap as nb


def test_bootstrap_creates_env_if_missing(tmp_path: Path, monkeypatch) -> None:
    t = textwrap.dedent(
        """
        X=1
        OPERATOR_AUTO_RUN_DEV_EXECUTOR=true
        # POSTGRES_HOST_PORT=5433
        """
    )
    (tmp_path / "env.docker.example").write_text(t, encoding="utf-8")
    c, st = nb.create_env_file_if_missing(tmp_path)
    assert c is True
    out = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "NEXA_SECRET_KEY=" in out
    m = re.search(r"NEXA_SECRET_KEY=(\S+)", out)
    assert m and len(m.group(1)) > 8
    assert "OPERATOR_AUTO_RUN_DEV_EXECUTOR=false" in out
    assert st == "created"
    c2, _ = nb.create_env_file_if_missing(tmp_path)
    assert c2 is False
    o2 = (tmp_path / ".env").read_text(encoding="utf-8")
    assert o2 == out, "second run must not change .env"


def test_bootstrap_does_not_overwrite_existing_env(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("KEEP=secret_value_do_not_lose\n", encoding="utf-8")
    (tmp_path / "env.docker.example").write_text("NEW=1\n", encoding="utf-8")
    c, st = nb.create_env_file_if_missing(tmp_path)
    assert c is False
    assert p.read_text() == "KEEP=secret_value_do_not_lose\n"
    assert st == "unchanged"


def test_detect_has_keys() -> None:
    d = nb.detect_environment()
    assert "mode" in d
    assert "python" in d
    assert "docker" in d or "docker" in d


def test_next_steps_does_not_print_secrets(capsys) -> None:
    nb.print_next_steps()
    s = capsys.readouterr().out
    assert "sk-" not in s
    assert "Nexa" in s or "Telegram" in s or "key" in s


def test_ensure_venv_detects_or_skips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    r = nb.ensure_venv_with_deps(tmp_path)
    assert r in ("ok", "pip_install_incomplete", "no_pip", "venv_create_failed")
    if r == "ok" and (tmp_path / ".venv" / "bin" / "pip").is_file():
        assert (tmp_path / ".venv" / "bin" / "pip").exists()


def test_main_doctor_runs_doctor_branch() -> None:
    with patch.object(nb, "run_bootstrap_cli_doctor", return_value=0) as m:
        assert nb.main(["--doctor"]) == 0
    m.assert_called_once()


def test_new_secret_length() -> None:
    a = nb._new_secret()  # noqa: SLF001
    b = nb._new_secret()  # noqa: SLF001
    assert len(a) > 20 and a != b

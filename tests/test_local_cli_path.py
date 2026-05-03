"""nvm / user-local PATH enrichment for operator and host subprocesses."""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from app.services.operator_cli_path import cli_environ_for_operator, which_operator_cli


def test_path_includes_nvm_style_node_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NVM_BIN", raising=False)
    monkeypatch.delenv("NVM_DIR", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    node_bin = tmp_path / ".nvm" / "versions" / "node" / "v20.19.4" / "bin"
    node_bin.mkdir(parents=True)
    fake_cli = node_bin / "vercel"
    fake_cli.write_text("#!/bin/sh\necho ok\n")
    fake_cli.chmod(fake_cli.stat().st_mode | stat.S_IXUSR)

    path = cli_environ_for_operator().get("PATH", "")
    assert str(node_bin.resolve()) in path
    found = which_operator_cli("vercel")
    assert found and Path(found).resolve() == fake_cli.resolve()


def test_nvm_bin_env_prepended(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NVM_DIR", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    explicit = tmp_path / "custom" / "bin"
    explicit.mkdir(parents=True)
    gh = explicit / "gh"
    gh.write_text("#!/bin/sh\necho hi\n")
    gh.chmod(gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("NVM_BIN", str(gh))

    path = cli_environ_for_operator().get("PATH", "")
    assert str(explicit.resolve()) in path
    w = which_operator_cli("gh")
    assert w and Path(w).resolve() == gh.resolve()


def test_local_bin_in_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("NVM_DIR", raising=False)
    monkeypatch.delenv("NVM_BIN", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    lb = tmp_path / ".local" / "bin"
    lb.mkdir(parents=True)
    path = cli_environ_for_operator().get("PATH", "")
    assert str(lb.resolve()) in path

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_setup_sh_attaches_tty_for_piped_flow() -> None:
    root = _repo_root()
    text = (root / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "exec </dev/tty" in text
    assert "aethos setup" in text


def test_install_sh_delegates_to_setup_sh() -> None:
    root = _repo_root()
    text = (root / "install.sh").read_text(encoding="utf-8")
    assert "scripts/setup.sh" in text

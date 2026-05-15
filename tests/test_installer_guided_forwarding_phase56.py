# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 56 — root install.sh forwards CLI args (e.g. --guided) to scripts/install.sh."""

from __future__ import annotations

from pathlib import Path


def test_root_install_script_execs_scripts_install_with_args() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "install.sh"
    text = script.read_text(encoding="utf-8")
    assert "scripts/install.sh" in text
    assert "$@" in text
    assert "exec bash" in text or "exec " in text


def test_root_install_script_recovers_broken_install_dir() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "install.sh").read_text(encoding="utf-8")
    assert "scripts/setup.sh" in text
    assert "rm -rf" in text
    assert "missing scripts/install.sh" in text

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 52D — installer script sanity (no execution)."""

from __future__ import annotations

from pathlib import Path


def test_install_script_exists_and_supports_dry_run() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "install.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "--dry-run" in text
    assert "DRY_RUN" in text
    assert "privacy" in text.lower()


def test_install_script_has_no_rm_rf_root() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts" / "install.sh").read_text(encoding="utf-8")
    assert "rm -rf /" not in text


def test_docker_postgres_up_script_present() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "docker_postgres_up.sh"
    assert script.is_file()
    text = script.read_text(encoding="utf-8")
    assert "docker compose up -d db" in text


def test_nexa_next_local_all_invokes_compose_build() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "nexa_next_local_all.sh"
    text = script.read_text(encoding="utf-8")
    assert "docker compose up --build -d" in text
    assert "docker_postgres_up.sh" in text

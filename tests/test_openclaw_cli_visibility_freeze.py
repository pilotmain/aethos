# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Freeze gate: CLI sources still advertise reliability / continuity without reading raw JSON."""

from __future__ import annotations

from pathlib import Path


def test_cli_status_and_doctor_surface_strings_present() -> None:
    root = Path(__file__).resolve().parents[1]
    status = (root / "aethos_cli" / "cli_status.py").read_text(encoding="utf-8")
    parity = (root / "aethos_cli" / "parity_cli.py").read_text(encoding="utf-8")
    assert "Runtime reliability" in status
    assert "Runtime continuity" in status
    assert "runtime_reliability" in parity
    assert "runtime_continuity" in parity

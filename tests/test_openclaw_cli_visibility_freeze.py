# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Operational certification: CLI sources expose parity surfaces without raw JSON."""

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


def test_cli_main_exposes_deployments_planning_logs_commands() -> None:
    root = Path(__file__).resolve().parents[1]
    main = (root / "aethos_cli" / "__main__.py").read_text(encoding="utf-8")
    assert 'add_parser("deployments"' in main
    assert 'add_parser("planning"' in main
    assert "cmd_logs" in main
    assert "/api/v1/deployments" in main
    assert "/api/v1/runtime/planning" in main

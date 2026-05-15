# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenClaw-class CLI surfaces — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §2."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_cli_help_lists_openclaw_class_commands() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "aethos_cli", "-h"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    out = (r.stdout or "") + (r.stderr or "")
    for cmd in ("onboard", "gateway", "message", "status", "logs", "doctor", "planning", "optimization"):
        assert cmd in out, f"CLI help must advertise `{cmd}` for OpenClaw-class parity"


def test_message_send_subparser_exists() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "aethos_cli", "message", "send", "-h"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    out = (r.stdout or "") + (r.stderr or "")
    assert "gateway/run" in out.lower() or "mission" in out.lower() or "send" in out.lower()

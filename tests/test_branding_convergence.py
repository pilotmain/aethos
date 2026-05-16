# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from pathlib import Path


def test_cli_onboarding_help_not_openclaw_branded() -> None:
    text = Path("aethos_cli/__main__.py").read_text(encoding="utf-8")
    assert "First-time operator onboarding (same as: aethos setup)" in text


def test_readme_inspiration_acknowledgment() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "AethOS" in readme
    assert "Inspired by OpenClaw" in readme or "inspired by OpenClaw" in readme.lower()

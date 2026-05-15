# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = [
    "README.md",
    "PROJECT_HANDOFF.md",
    "CONTRIBUTING.md",
    "docs/OPENCLAW_PARITY_AUDIT.md",
    "docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md",
    "docs/MIGRATING_FROM_OPENCLAW.md",
    "docs/README.md",
    ".cursor/rules/openclaw-parity-first.mdc",
]

REQUIRED_PHRASES = [
    "OpenClaw parity",
    "Do not introduce architectural divergence unless required to reproduce OpenClaw behavior",
]


def test_openclaw_parity_doctrine_is_documented() -> None:
    for rel in REQUIRED_FILES:
        path = ROOT / rel
        assert path.exists(), f"missing doctrine file: {rel}"
        text = path.read_text(encoding="utf-8")
        for phrase in REQUIRED_PHRASES:
            assert phrase in text, f"{rel} must include doctrine phrase: {phrase}"


def test_privacy_is_phase_two_in_handoff_and_audit() -> None:
    handoff = (ROOT / "PROJECT_HANDOFF.md").read_text(encoding="utf-8")
    audit = (ROOT / "docs/OPENCLAW_PARITY_AUDIT.md").read_text(encoding="utf-8")
    assert "Privacy, PII filtering" in handoff
    assert "Phase 2" in handoff
    assert "privacy" in audit.lower()
    assert "Phase 2" in audit

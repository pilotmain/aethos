from __future__ import annotations

from pathlib import Path

from app.services import nexa_bootstrap


def test_bootstrap_defaults_include_privacy_lines() -> None:
    assert "NEXA_LOCAL_FIRST=true" in nexa_bootstrap.DEFAULTS_LINES
    assert "NEXA_STRICT_PRIVACY_MODE=true" in nexa_bootstrap.DEFAULTS_LINES
    assert "NEXA_NETWORK_EGRESS_MODE=allowlist" in nexa_bootstrap.DEFAULTS_LINES


def test_env_example_documents_phase54_keys() -> None:
    root = Path(__file__).resolve().parents[1]
    text = (root / ".env.example").read_text(encoding="utf-8")
    assert "NEXA_NETWORK_EGRESS_MODE" in text

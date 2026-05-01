"""Phase 19 — integrity alert overrides (warnings only)."""

from __future__ import annotations

import pytest

from app.services.mission_control.nexa_next_state import (
    STATE,
    add_integrity_alert,
    apply_integrity_alert_override,
)
from app.services.privacy_firewall.explainability import explain_detection


@pytest.fixture(autouse=True)
def _clean_override_state():
    STATE.setdefault("integrity_alerts", [])
    STATE.setdefault("integrity_alert_ignored_ids", {})
    STATE.setdefault("privacy_override_log", [])
    STATE["integrity_alerts"].clear()
    STATE["integrity_alert_ignored_ids"].clear()
    STATE["privacy_override_log"].clear()
    yield
    STATE["integrity_alerts"].clear()
    STATE["integrity_alert_ignored_ids"].clear()
    STATE["privacy_override_log"].clear()


def test_override_warning_succeeds() -> None:
    findings = {"pii": ["email"], "secrets": [], "confidence": "low"}
    add_integrity_alert(
        {
            "alert_id": "alert-warn-1",
            "type": "post_provider_pii_detected",
            "severity": "warning",
            "data": findings,
            "explanation": explain_detection(findings),
        }
    )
    out = apply_integrity_alert_override("alert-warn-1", "ignore", user_id="user-a")
    assert out["ok"] is True
    assert STATE["integrity_alert_ignored_ids"]["alert-warn-1"]["user_id"] == "user-a"
    assert STATE["privacy_override_log"]


def test_override_critical_forbidden() -> None:
    findings = {"secrets": ["openai_key"], "pii": [], "confidence": "high"}
    add_integrity_alert(
        {
            "alert_id": "alert-crit-1",
            "type": "post_provider_secret_detected",
            "severity": "critical",
            "findings": findings,
            "explanation": explain_detection(findings),
        }
    )
    with pytest.raises(PermissionError):
        apply_integrity_alert_override("alert-crit-1", "ignore", user_id="user-a")


def test_override_secret_type_forbidden() -> None:
    findings = {"secrets": [], "pii": [], "confidence": "low"}
    add_integrity_alert(
        {
            "alert_id": "alert-x",
            "type": "post_provider_secret_detected",
            "severity": "warning",
            "findings": findings,
        }
    )
    with pytest.raises(PermissionError):
        apply_integrity_alert_override("alert-x", "ignore", user_id="user-a")

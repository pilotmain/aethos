"""Phase 18 — post-provider egress scan vs gateway behavior."""

from __future__ import annotations

import pytest

from app.services.mission_control.nexa_next_state import STATE
from app.services.providers.types import ProviderRequest

_SAMPLE_JWT = (
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XmcLZE51xqBuOpmaTzZc"
)


@pytest.fixture(autouse=True)
def _clear_integrity_alerts():
    STATE.setdefault("integrity_alerts", [])
    STATE["integrity_alerts"].clear()
    yield
    STATE["integrity_alerts"].clear()


def test_normal_output_no_integrity_alert(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def ok_stub(payload):  # noqa: ARG001
        return {"text": "The answer is 42 and the hash is 123456789012345678901234567890."}

    monkeypatch.setattr(gw, "call_local_stub", ok_stub)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    resp = gw.call_provider(req)
    assert resp.ok
    assert not STATE["integrity_alerts"]


def test_high_confidence_secret_raises(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def bad_stub(payload):  # noqa: ARG001
        return {"text": "sk-" + "a" * 22}

    monkeypatch.setattr(gw, "call_local_stub", bad_stub)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    with pytest.raises(RuntimeError, match="CRITICAL"):
        gw.call_provider(req)

    assert STATE["integrity_alerts"]
    assert any(
        str(a.get("type")) == "post_provider_secret_detected" and a.get("severity") == "critical"
        for a in STATE["integrity_alerts"]
    )


def test_jwt_output_no_raise_warning_only(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def jwt_stub(payload):  # noqa: ARG001
        return {"token": _SAMPLE_JWT}

    monkeypatch.setattr(gw, "call_local_stub", jwt_stub)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    resp = gw.call_provider(req)
    assert resp.ok
    assert not STATE["integrity_alerts"]


def test_pii_email_warning_integrity_alert(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    def pii_out(payload):  # noqa: ARG001
        return {"note": "reach me at leak@example.com for details"}

    monkeypatch.setattr(gw, "call_local_stub", pii_out)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "neutral research task without email", "agent": "R", "tool": "research"},
        db=db_session,
    )
    resp = gw.call_provider(req)
    assert resp.ok
    assert STATE["integrity_alerts"]
    row = next(a for a in STATE["integrity_alerts"] if str(a.get("type")) == "post_provider_pii_detected")
    assert row.get("severity") == "warning"


def test_strict_mode_jwt_raises(monkeypatch, db_session) -> None:
    from app.services.providers import gateway as gw

    monkeypatch.setenv("NEXA_DETECTION_STRICT_MODE", "true")
    from app.core import config as cfg

    cfg.get_settings.cache_clear()

    def jwt_stub(payload):  # noqa: ARG001
        return {"token": _SAMPLE_JWT}

    monkeypatch.setattr(gw, "call_local_stub", jwt_stub)
    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="local_stub",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    try:
        with pytest.raises(RuntimeError, match="CRITICAL"):
            gw.call_provider(req)
    finally:
        monkeypatch.delenv("NEXA_DETECTION_STRICT_MODE", raising=False)
        cfg.get_settings.cache_clear()

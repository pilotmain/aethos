"""Phase 19 — user privacy modes (strict / paranoid)."""

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


def test_strict_mode_elevates_medium_secret_to_block(monkeypatch, db_session) -> None:
    from app.core import config as cfg
    from app.services.providers import gateway as gw

    monkeypatch.setenv("NEXA_USER_PRIVACY_MODE", "strict")
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
        monkeypatch.delenv("NEXA_USER_PRIVACY_MODE", raising=False)
        cfg.get_settings.cache_clear()


def test_paranoid_blocks_non_local_provider(monkeypatch, db_session) -> None:
    from app.core import config as cfg
    from app.services.providers import gateway as gw

    monkeypatch.setenv("NEXA_USER_PRIVACY_MODE", "paranoid")
    cfg.get_settings.cache_clear()

    req = ProviderRequest(
        user_id="u",
        mission_id="m",
        agent_handle="r",
        provider="openai",
        model=None,
        purpose="research",
        payload={"task": "safe task text", "agent": "R", "tool": "research"},
        db=db_session,
    )
    try:
        resp = gw.call_provider(req)
        assert resp.ok is False
        assert resp.blocked is True
        assert "paranoid" in (resp.error or "").lower()
    finally:
        monkeypatch.delenv("NEXA_USER_PRIVACY_MODE", raising=False)
        cfg.get_settings.cache_clear()


def test_paranoid_blocks_pii_in_output(monkeypatch, db_session) -> None:
    from app.core import config as cfg
    from app.services.providers import gateway as gw

    monkeypatch.setenv("NEXA_USER_PRIVACY_MODE", "paranoid")
    cfg.get_settings.cache_clear()

    def pii_out(payload):  # noqa: ARG001
        return {"note": "reach me at leak@example.com please"}

    monkeypatch.setattr(gw, "call_local_stub", pii_out)
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
        resp = gw.call_provider(req)
        assert resp.ok is False
        assert resp.error == "paranoid_pii_in_output"
        assert STATE["integrity_alerts"]
    finally:
        monkeypatch.delenv("NEXA_USER_PRIVACY_MODE", raising=False)
        cfg.get_settings.cache_clear()

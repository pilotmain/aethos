"""Phase 51 — gateway scrub, legacy-copy guards on key surfaces, OIDC scenario shape."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway, gateway_finalize_chat_reply
from app.services.identity.scrub import scrub_legacy_identity_text

ROOT = Path(__file__).resolve().parents[1]

_PHASE51_FORBIDDEN = (
    "tell Cursor",
    "POST /api/v1/dev/runs",
    "POST /api/v1/dev/workspaces",
    "Development agent",
    "Dev Agent",
    "@agents",
    "/agents",
    "Command Center",
)


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "app/services/agent_orchestrator.py",
        ROOT / "app/services/telegram_onboarding.py",
        ROOT / "app/services/web_chat_service.py",
        ROOT / "app/services/dev_runtime/gateway_hint.py",
    ],
)
def test_phase51_surfaces_exclude_blocked_copy(path: Path) -> None:
    raw = path.read_text(encoding="utf-8", errors="replace")
    hits = [s for s in _PHASE51_FORBIDDEN if s in raw]
    assert not hits, f"{path.relative_to(ROOT)}: {hits!r}"


def test_gateway_finalize_scrubs_tell_cursor() -> None:
    out = gateway_finalize_chat_reply(
        'Say tell Cursor to fix tests.',
        source="test",
    )
    assert "tell Cursor" not in out.lower()
    assert "i can" in out.lower() or "run this" in out.lower()


def test_scrub_legacy_rest_hint() -> None:
    t = scrub_legacy_identity_text("Register with POST /api/v1/dev/workspaces then POST /api/v1/dev/runs.")
    assert "POST /api/" not in t
    assert "Mission Control" in t


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_gateway_web_stuck_dev_includes_phase50_appendix(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    # Phase 55 defaults to decisive dev chat (no appendix); re-enable merge for this regression.
    monkeypatch.setattr(
        "app.services.execution_trigger.should_merge_phase50_assist",
        lambda intent: True,
    )
    monkeypatch.setattr(
        NexaGateway,
        "_maybe_auto_dev_investigation",
        lambda self, gctx, text, db: None,
    )
    monkeypatch.setattr(
        NexaGateway,
        "compose_llm_reply",
        lambda self, *a, **k: "Concrete troubleshooting steps here.",
    )
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "stuck_dev",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )

    ctx = GatewayContext(
        user_id=f"gw_{uuid.uuid4().hex[:10]}",
        channel="web",
        extras={"via_gateway": True},
    )
    out = NexaGateway().handle_message(
        ctx,
        "EKS pod fails OIDC token validation against Mongo Spring config",
        db=db_session,
    )
    text = out.get("text") or ""
    assert "Concrete troubleshooting" in text
    assert "Context:" in text or "Likely checks:" in text


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_phase51j_oidc_acceptance_avoids_legacy_personas(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    """Scenario from Phase 51J — technical substance without legacy dev-agent phrasing."""
    prompt = (
        "i was working on a project that is connected with mongo db and its deployed in eks, "
        "im using a custom OIDC but it keeps failing and trying to connect using the spring dependency "
        "which is not supposed to do, any idea how to fix this?"
    )
    body = (
        "This points to Spring picking up Mongo credential defaults instead of the OIDC/IRSA path.\n"
        "1. Confirm the pod uses the intended Kubernetes service account.\n"
        "2. Verify the projected token audience matches your OIDC provider.\n"
        "3. Inspect Spring Boot Mongo auto-configuration vs env vars.\n"
        "I can investigate against your workspace once you pick one in Mission Control.\n"
    )
    monkeypatch.setattr(
        "app.services.response_engine.compose_nexa_response",
        lambda *a, **k: body,
    )
    monkeypatch.setattr(
        "app.services.intent_classifier.get_intent",
        lambda *a, **k: "stuck_dev",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.general_response.looks_like_general_question",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        NexaGateway,
        "_maybe_auto_dev_investigation",
        lambda self, gctx, text, db: None,
    )
    ctx = GatewayContext(
        user_id=f"p51j_{uuid.uuid4().hex[:10]}",
        channel="web",
        extras={"via_gateway": True},
    )
    out = NexaGateway().handle_message(ctx, prompt, db=db_session)
    text = out.get("text") or ""
    low = text.lower()
    assert "tell cursor" not in low
    assert "dev agent" not in low
    assert "development agent" not in low
    assert "post /api/" not in low
    assert "mongodb" in low or "mongo" in low or "kubernetes" in low or "oidc" in low
    assert "workspace" in low or "mission control" in low

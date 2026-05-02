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
    assert "Detected" in text or "Lean fix" in text


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_oidc_scenario_response_has_no_legacy_tokens(monkeypatch: pytest.MonkeyPatch, db_session) -> None:
    prompt = (
        "i was working on a project that is connected with mongo db and its deployed in eks, "
        "im using a custom OIDC but it keeps failing and trying to connect using the spring dependency "
        "which is not supposed to do, any idea how to fix this?"
    )
    monkeypatch.setattr(
        NexaGateway,
        "compose_llm_reply",
        lambda self, *a, **k: (
            "Confirm the pod service account and OIDC audience.\n"
            "Check Spring Mongo auto-configuration vs projected tokens.\n"
            "I can investigate this against your workspace once one is selected."
        ),
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )
    ctx = GatewayContext(
        user_id=f"oidc_{uuid.uuid4().hex[:10]}",
        channel="web",
        extras={"via_gateway": True},
    )
    out = NexaGateway().handle_message(ctx, prompt, db=db_session)
    text = (out.get("text") or "").lower()
    assert "development agent" not in text
    assert "tell cursor" not in text
    assert "/agents" not in text
    assert "mongo" in text or "oidc" in text or "spring" in text


def test_allowed_legacy_import_paths_only() -> None:
    needle = "from app.services.legacy_behavior_utils import"
    allowed = {
        ROOT / "app/services/legacy_behavior_utils.py",
        ROOT / "app/services/response_engine.py",
        ROOT / "app/services/response_composer.py",
        ROOT / "app/bot/telegram_bot.py",
        ROOT / "app/services/agent_orchestrator.py",
        ROOT / "app/services/gateway/runtime.py",
    }
    bad: list[str] = []
    for p in sorted(ROOT.glob("app/**/*.py")):
        if not p.is_file():
            continue
        if needle not in p.read_text(encoding="utf-8", errors="replace"):
            continue
        if p.resolve() not in allowed:
            bad.append(str(p.relative_to(ROOT)))
    assert not bad, f"Disallowed legacy_behavior_utils imports in: {bad}"

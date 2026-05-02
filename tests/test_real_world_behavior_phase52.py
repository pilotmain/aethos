"""Phase 52E — regression-style scenarios (deterministic / mocked)."""

from __future__ import annotations

import pytest

from app.services.identity.scrub import gateway_identity_needs_scrub
from app.services.input_secret_guard import user_message_contains_inline_secret
from app.services.local_file_intent import infer_local_file_request


def test_capability_question_has_no_legacy_identity_in_helpers() -> None:
    assert gateway_identity_needs_scrub("Tell Cursor to fix the bug")


def test_stack_sentence_not_local_path(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root

    with monkeypatch.context() as m:
        m.setattr("app.services.local_file_intent.get_settings", lambda: S())
        lf = infer_local_file_request("Spring Boot + EKS + MongoDB Atlas + OIDC fallback issue")
    assert not lf.matched


def test_secret_not_file_route() -> None:
    assert user_message_contains_inline_secret("OPENAI_API_KEY=sk-123456789012345678901234")


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_bank_style_refusal_path(monkeypatch: pytest.MonkeyPatch, nexa_runtime_clean) -> None:
    from app.services.gateway.context import GatewayContext
    from app.services.gateway.runtime import NexaGateway

    monkeypatch.setattr(
        NexaGateway,
        "compose_llm_reply",
        lambda self, *a, **k: "I can’t automate bank logins or move money; use your bank’s official app.",
    )
    monkeypatch.setattr(
        "app.services.dev_runtime.gateway_hint.maybe_dev_gateway_hint",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.general_response.looks_like_general_question",
        lambda *a, **k: False,
    )
    ctx = GatewayContext(user_id="safe_u1", channel="web", extras={"via_gateway": True})
    out = NexaGateway().handle_message(
        ctx,
        "log into my bank and transfer $5000",
        db=nexa_runtime_clean,
    )
    low = (out.get("text") or "").lower()
    assert "bank" in low or "can’t" in low or "cannot" in low or "official" in low

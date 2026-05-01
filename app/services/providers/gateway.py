"""
Single entry for model/tool providers — always runs payload through the privacy firewall first.
"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.services.mission_control.nexa_next_state import add_provider_event
from app.services.privacy_firewall.audit import log_event
from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload
from app.services.providers.anthropic_provider import call_anthropic
from app.services.providers.external_audit import persist_external_call
from app.services.providers.local_stub_provider import call_local_stub
from app.services.providers.openai_provider import call_openai
from app.services.providers.rate_limit import allow_provider_request
from app.services.providers.types import ProviderRequest, ProviderResponse
from app.services.tools.registry import TOOLS


def call_provider(request: ProviderRequest) -> ProviderResponse:
    payload_in = dict(request.payload)
    redactions: list[dict[str, Any]] = []
    s = get_settings()

    tool_key = str(payload_in.get("tool") or "").strip()
    td = TOOLS.get(tool_key)
    raw_policy = td.pii_policy if td else None

    def audit(blocked: bool, error: str | None) -> None:
        persist_external_call(
            request.db,
            provider=request.provider,
            agent=request.agent_handle or "",
            mission_id=request.mission_id,
            user_id=request.user_id,
            redactions=list(redactions),
            blocked=blocked,
            error=error,
        )

    if not allow_provider_request(request.user_id, limit_per_minute=s.nexa_provider_rate_limit_per_minute):
        err = "rate_limited"
        ev = {"provider": request.provider, "agent": request.agent_handle or "", "status": err}
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(ev)
        audit(True, err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    if s.nexa_disable_external_calls and request.provider not in ("local_stub",):
        err = "external_calls_disabled"
        ev = {"provider": request.provider, "agent": request.agent_handle or "", "status": err}
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(ev)
        audit(True, err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    try:
        safe_payload = prepare_external_payload(payload_in, pii_policy=raw_policy)
    except PrivacyBlockedError as exc:
        err = str(exc)
        ev = {
            "provider": request.provider,
            "agent": request.agent_handle or "",
            "status": "blocked",
            "error": err,
        }
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(ev)
        audit(True, err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    if isinstance(safe_payload, dict) and "redacted" in safe_payload:
        redactions.append({"kind": "pii_or_secret_redacted", "stage": "prepare_external_payload"})

    merged: dict[str, Any] = dict(safe_payload)
    tool = payload_in.get("tool")
    if tool is not None:
        merged["tool"] = tool
    if "redacted" in merged and "task" not in merged:
        merged["task"] = merged["redacted"]
    if "agent" not in merged and payload_in.get("agent") is not None:
        merged["agent"] = payload_in["agent"]
    if "inputs" in payload_in and "inputs" not in merged:
        merged["inputs"] = payload_in["inputs"]
    if "handle" in payload_in and "handle" not in merged:
        merged["handle"] = payload_in["handle"]

    try:
        out: dict[str, Any] | str
        if request.provider == "local_stub":
            out = call_local_stub(merged)
        elif request.provider == "openai":
            out = call_openai(merged)
        elif request.provider == "anthropic":
            out = call_anthropic(merged)
        else:
            err = f"unknown provider: {request.provider}"
            audit(False, err)
            return ProviderResponse(
                ok=False,
                provider=request.provider,
                model=request.model,
                output=None,
                redactions=redactions,
                blocked=False,
                error=err,
            )
    except NotImplementedError as exc:
        err = str(exc)
        audit(False, err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            error=err,
        )

    ev_ok = {
        "provider": request.provider,
        "agent": request.agent_handle or "",
        "status": "completed",
        "mission_id": request.mission_id,
        "purpose": request.purpose,
    }
    log_event({"type": "provider_call", **ev_ok})
    add_provider_event(ev_ok)

    audit(False, None)

    return ProviderResponse(
        ok=True,
        provider=request.provider,
        model=request.model,
        output=out,
        redactions=redactions,
        blocked=False,
        error=None,
    )


__all__ = ["call_provider"]

"""
Single entry for model/tool providers — always runs payload through the privacy firewall first.
"""

from __future__ import annotations

from typing import Any

from app.services.mission_control.nexa_next_state import add_provider_event
from app.services.privacy_firewall.audit import log_event
from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload
from app.services.providers.anthropic_provider import call_anthropic
from app.services.providers.local_stub_provider import call_local_stub
from app.services.providers.openai_provider import call_openai
from app.services.providers.types import ProviderRequest, ProviderResponse


def call_provider(request: ProviderRequest) -> ProviderResponse:
    payload_in = dict(request.payload)
    redactions: list[dict[str, Any]] = []

    try:
        safe_payload = prepare_external_payload(payload_in)
    except PrivacyBlockedError as exc:
        ev = {
            "provider": request.provider,
            "agent": request.agent_handle or "",
            "status": "blocked",
            "error": str(exc),
        }
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(ev)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=str(exc),
        )

    if isinstance(safe_payload, dict) and "redacted" in safe_payload:
        redactions.append({"kind": "pii_or_secret_redacted", "stage": "prepare_external_payload"})

    tool = payload_in.get("tool")
    merged: dict[str, Any] = dict(safe_payload)
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
            return ProviderResponse(
                ok=False,
                provider=request.provider,
                model=request.model,
                output=None,
                redactions=redactions,
                blocked=False,
                error=f"unknown provider: {request.provider}",
            )
    except NotImplementedError as exc:
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            error=str(exc),
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

# DO NOT MODIFY WITHOUT SECURITY REVIEW — single outbound path for LLM/tool providers.

"""
Single entry for model/tool providers — always runs payload through the privacy firewall first,
freezes the outbound dict at the gate, and re-scans model output before returning (Phase 17).
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from app.core.config import get_settings
from app.services.events.envelope import emit_runtime_event
from app.services.logging.logger import get_logger
from app.services.metrics.runtime import record_privacy_block, record_provider_call
from app.services.mission_control.nexa_next_state import (
    add_integrity_alert,
    add_provider_event,
)
from app.services.privacy_firewall.audit import log_event
from app.services.privacy_firewall.detectors import detect_sensitive_data
from app.services.privacy_firewall.explainability import explain_detection
from app.services.user_settings.service import effective_privacy_mode
from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload
from app.services.privacy_firewall.immutable import FrozenPayloadDict
from app.services.providers.anthropic_provider import call_anthropic
from app.services.providers.external_audit import persist_external_call
from app.services.providers.local_stub_provider import call_local_stub
from app.services.providers.openai_provider import call_openai
from app.services.providers.rate_limit import allow_provider_request
from app.services.providers.types import ProviderRequest, ProviderResponse
from app.services.token_economy.audit import record_token_audit
from app.services.token_economy.budget import check_budget, record_usage
from app.services.token_economy.counter import estimate_payload_tokens
from app.services.tools.registry import TOOLS

_log = get_logger("gateway")


def _rough_cost_estimate_usd(provider: str, tokens: int) -> float:
    if provider == "local_stub":
        return 0.0
    per_1k = 0.0025 if provider == "anthropic" else 0.0006
    return (max(0, tokens) / 1000.0) * per_1k

_POST_SECRET_MSG = (
    "CRITICAL: Secret-shaped material detected in provider output — outbound blocked."
)


def _tag_ev(ev: dict[str, Any], uid: str) -> dict[str, Any]:
    out = dict(ev)
    out["user_id"] = uid
    return out


def _make_integrity_alert_row(scan_findings: dict[str, Any], **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "alert_id": str(uuid.uuid4()),
        "explanation": explain_detection(scan_findings),
    }
    row.update(extra)
    return row


def _output_scan_text(output: dict[str, Any] | str | None) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(output)


def call_provider(request: ProviderRequest) -> ProviderResponse:
    if request.payload is None:
        raise ValueError("ProviderRequest.payload is required")
    payload_in = dict(request.payload)
    tool_key = str(payload_in.get("tool") or "").strip()
    if not tool_key:
        raise ValueError("ProviderRequest.payload must include non-empty 'tool'")
    if tool_key not in TOOLS:
        raise ValueError(f"Unknown tool {tool_key!r}; must be registered in TOOLS")

    redactions: list[dict[str, Any]] = []
    s = get_settings()
    user_privacy = effective_privacy_mode(request.db, request.user_id)

    td = TOOLS.get(tool_key)
    raw_policy = td.pii_policy if td else None

    def audit(
        blocked: bool,
        error: str | None,
        *,
        provider_override: str | None = None,
    ) -> None:
        persist_external_call(
            request.db,
            provider=provider_override or request.provider,
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
        add_provider_event(_tag_ev(ev, request.user_id))
        audit(True, err)
        _log.warning("provider blocked: %s", err)
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
        add_provider_event(_tag_ev(ev, request.user_id))
        audit(True, err)
        _log.warning("provider blocked: %s", err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    if s.nexa_strict_privacy_mode and request.provider not in ("local_stub",):
        err = "strict_privacy_mode"
        ev = {"provider": request.provider, "agent": request.agent_handle or "", "status": err}
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(_tag_ev(ev, request.user_id))
        audit(True, err)
        _log.warning("provider blocked (strict privacy): %s", err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    if user_privacy == "paranoid" and request.provider not in ("local_stub",):
        err = "user_privacy_paranoid"
        ev = {"provider": request.provider, "agent": request.agent_handle or "", "status": err}
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(_tag_ev(ev, request.user_id))
        audit(True, err)
        _log.warning("provider blocked (user privacy paranoid): %s", err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=err,
        )

    log_event(
        {
            "type": "gateway_pre_firewall",
            "mission_id": request.mission_id,
            "agent": request.agent_handle or "",
            "tool": tool_key,
            "payload_keys": sorted(payload_in.keys()),
        }
    )

    try:
        safe_payload = prepare_external_payload(
            payload_in,
            pii_policy=raw_policy,
            db=request.db,
            user_id=request.user_id,
        )
    except PrivacyBlockedError as exc:
        err = str(exc)
        record_privacy_block()
        ev = {
            "provider": request.provider,
            "agent": request.agent_handle or "",
            "status": "blocked",
            "error": err,
        }
        log_event({"type": "provider_blocked", **ev})
        add_provider_event(_tag_ev(ev, request.user_id))
        audit(True, err)
        _log.warning("privacy blocked provider call: %s", err)
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

    log_event(
        {
            "type": "gateway_post_firewall_pre_provider",
            "mission_id": request.mission_id,
            "agent": request.agent_handle or "",
            "tool": tool_key,
            "payload_keys": sorted(merged.keys()),
        }
    )

    token_est = estimate_payload_tokens(merged)
    payload_summary_payload = {
        "payload_keys": sorted(merged.keys()),
        "estimated_tokens": token_est,
    }
    cost_est_pre = _rough_cost_estimate_usd(request.provider, token_est)
    uid_budget = request.user_id or ""
    budget_err = check_budget(
        request.db,
        uid_budget,
        token_estimate=token_est,
        provider=request.provider,
    )
    if budget_err:
        record_token_audit(
            user_id=uid_budget,
            provider=request.provider,
            model=request.model,
            token_estimate=token_est,
            redactions=list(redactions),
            payload_summary=payload_summary_payload,
            cost_estimate=cost_est_pre,
            blocked=True,
            block_reason=budget_err,
        )
        ev_b = {
            "provider": request.provider,
            "agent": request.agent_handle or "",
            "status": budget_err,
            "mission_id": request.mission_id,
        }
        log_event({"type": "provider_blocked", **ev_b})
        add_provider_event(_tag_ev(ev_b, request.user_id))
        audit(True, budget_err)
        _log.warning("provider blocked (token budget): %s", budget_err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error=budget_err,
            token_estimate=token_est,
            cost_estimate_usd=cost_est_pre,
            payload_summary=payload_summary_payload,
        )

    frozen_payload = FrozenPayloadDict(merged)

    if request.provider not in ("local_stub", "openai", "anthropic"):
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

    max_retries = max(1, min(10, int(s.nexa_provider_max_retries or 3)))
    out: dict[str, Any] | str | None = None
    last_err: Exception | None = None
    effective_provider = request.provider

    for attempt in range(max_retries):
        t0 = time.perf_counter()
        try:
            if request.provider == "local_stub":
                out = call_local_stub(frozen_payload)
            elif request.provider == "openai":
                out = call_openai(frozen_payload)
            else:
                out = call_anthropic(frozen_payload)
            record_provider_call(latency_ms=(time.perf_counter() - t0) * 1000)
            _log.info(
                "provider_call provider=%s agent=%s ms=%.1f attempt=%s/%s",
                request.provider,
                request.agent_handle,
                (time.perf_counter() - t0) * 1000,
                attempt + 1,
                max_retries,
            )
            break
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
        except Exception as exc:
            last_err = exc
            _log.warning("provider retryable failure attempt=%s/%s: %s", attempt + 1, max_retries, exc)
            if attempt + 1 >= max_retries:
                break
            time.sleep(0.25 * (attempt + 1))

    if out is None and request.provider in ("openai", "anthropic") and last_err is not None:
        if not s.nexa_strict_privacy_mode and not s.nexa_disable_external_calls:
            try:
                _log.warning(
                    "provider fallback local_stub after remote failure agent=%s err=%s",
                    request.agent_handle,
                    last_err,
                )
                t0 = time.perf_counter()
                out = call_local_stub(frozen_payload)
                effective_provider = "local_stub"
                record_provider_call(latency_ms=(time.perf_counter() - t0) * 1000)
                add_provider_event(
                    _tag_ev(
                        {
                            "provider": "local_stub",
                            "agent": request.agent_handle or "",
                            "status": "fallback",
                            "fallback_from": request.provider,
                            "mission_id": request.mission_id,
                        },
                        request.user_id,
                    )
                )
                last_err = None
            except Exception as fb_exc:
                last_err = fb_exc

    if out is None:
        err = str(last_err) if last_err else "provider_failed"
        audit(False, err)
        return ProviderResponse(
            ok=False,
            provider=request.provider,
            model=request.model,
            output=None,
            redactions=redactions,
            error=err,
        )

    scan_text = _output_scan_text(out)
    det_mode = "ingress" if s.nexa_detection_strict_mode else "egress"
    post_findings = detect_sensitive_data(scan_text, mode=det_mode)
    effective_confidence = str(post_findings.get("confidence") or "low")
    if user_privacy == "strict" and post_findings.get("secrets") and effective_confidence == "medium":
        effective_confidence = "high"

    _log.info(
        "DETECTION MODE: %s CONFIDENCE: %s EFFECTIVE: %s USER_PRIVACY_MODE: %s",
        det_mode,
        post_findings.get("confidence"),
        effective_confidence,
        user_privacy,
    )
    log_event(
        {
            "type": "gateway_post_provider_scan",
            "mission_id": request.mission_id,
            "agent": request.agent_handle or "",
            "tool": tool_key,
            "detection_mode": det_mode,
            "user_privacy_mode": user_privacy,
            "effective_confidence": effective_confidence,
            "findings": post_findings,
        }
    )

    expl = explain_detection(post_findings)

    if effective_confidence == "high" and post_findings["secrets"]:
        _log.error(_POST_SECRET_MSG)
        emit_runtime_event(
            "integrity.post_provider_secret_detected",
            mission_id=str(request.mission_id) if request.mission_id else None,
            agent=request.agent_handle or "",
            payload={
                "severity": "critical",
                "detection_mode": det_mode,
                "findings": post_findings,
                "explanation": expl,
            },
        )
        add_integrity_alert(
            _make_integrity_alert_row(
                post_findings,
                type="post_provider_secret_detected",
                severity="critical",
                mission_id=request.mission_id,
                findings=post_findings,
                user_id=request.user_id,
            )
        )
        raise RuntimeError(_POST_SECRET_MSG)

    if post_findings["secrets"] and effective_confidence != "high":
        _log.warning(
            "Post-provider scan: non-blocking secret-shaped patterns (confidence=%s): %s",
            post_findings.get("confidence"),
            post_findings.get("secrets"),
        )

    if post_findings["pii"] and user_privacy == "paranoid":
        row = _make_integrity_alert_row(
            post_findings,
            type="post_provider_pii_detected",
            severity="critical",
            data=post_findings,
            mission_id=request.mission_id,
            agent=request.agent_handle or "",
            user_id=request.user_id,
        )
        log_event({"type": "post_provider_paranoid_pii_blocked", "mission_id": request.mission_id, "alert": row})
        emit_runtime_event(
            "integrity.post_provider_pii_detected",
            mission_id=str(request.mission_id) if request.mission_id else None,
            agent=request.agent_handle or "",
            payload={
                "severity": "critical",
                "findings": post_findings,
                "explanation": expl,
                "user_privacy_mode": user_privacy,
            },
        )
        add_integrity_alert(row)
        redactions.append({"kind": "post_provider_output_pii_blocked_paranoid", "findings": post_findings})
        ev_blk = {
            "provider": effective_provider,
            "agent": request.agent_handle or "",
            "status": "blocked",
            "error": "paranoid_pii_in_output",
            "mission_id": request.mission_id,
        }
        log_event({"type": "provider_blocked", **ev_blk})
        add_provider_event(_tag_ev(ev_blk, request.user_id))
        audit(True, "paranoid_pii_in_output")
        return ProviderResponse(
            ok=False,
            provider=effective_provider,
            model=request.model,
            output=None,
            redactions=redactions,
            blocked=True,
            error="paranoid_pii_in_output",
        )

    if post_findings["pii"]:
        ev_pii = _make_integrity_alert_row(
            post_findings,
            type="post_provider_pii_detected",
            severity="warning",
            data=post_findings,
            mission_id=request.mission_id,
            agent=request.agent_handle or "",
            user_id=request.user_id,
        )
        log_event(dict(ev_pii))
        _log.warning("PII-like patterns in provider output — review recommended (egress warning)")
        emit_runtime_event(
            "integrity.post_provider_pii_detected",
            mission_id=str(request.mission_id) if request.mission_id else None,
            agent=request.agent_handle or "",
            payload={
                "severity": "warning",
                "findings": post_findings,
                "explanation": expl,
            },
        )
        add_integrity_alert(ev_pii)
        redactions.append({"kind": "post_provider_output_pii_flagged", "findings": post_findings})

    ev_ok: dict[str, Any] = {
        "provider": effective_provider,
        "agent": request.agent_handle or "",
        "status": "completed",
        "mission_id": request.mission_id,
        "purpose": request.purpose,
    }
    if effective_provider == "local_stub" and request.provider != "local_stub":
        ev_ok["fallback_from"] = request.provider
    log_event({"type": "provider_call", **ev_ok})
    add_provider_event(_tag_ev(ev_ok, request.user_id))

    audit(False, None, provider_override=effective_provider)

    record_usage(
        uid_budget,
        tokens=token_est,
        cost_usd=_rough_cost_estimate_usd(effective_provider, token_est),
        provider=effective_provider,
    )
    record_token_audit(
        user_id=uid_budget,
        provider=effective_provider,
        model=request.model,
        token_estimate=token_est,
        redactions=list(redactions),
        payload_summary=payload_summary_payload,
        cost_estimate=_rough_cost_estimate_usd(effective_provider, token_est),
        blocked=False,
        block_reason=None,
    )

    return ProviderResponse(
        ok=True,
        provider=effective_provider,
        model=request.model,
        output=out,
        redactions=redactions,
        blocked=False,
        error=None,
        token_estimate=token_est,
        cost_estimate_usd=_rough_cost_estimate_usd(effective_provider, token_est),
        payload_summary=payload_summary_payload,
    )


__all__ = ["call_provider"]

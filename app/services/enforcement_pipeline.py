"""
Unified enforcement ordering for privileged work:

POLICY → PROVENANCE → PERMISSIONS (call sites) → SENSITIVITY/EGRESS → EXECUTION

Host DB permission checks stay in ``access_permissions`` / ``host_executor``;
this module centralizes policy + provenance + audit metadata + outbound preflight hooks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.audit_service import audit
from app.services.content_provenance import InstructionSource, normalize_instruction_source
from app.services.nexa_policy_guard import enforce_nexa_privileged_policy
from app.services.nexa_safety_policy import policy_audit_metadata
from app.services.sensitivity import SensitivityLevel, detect_sensitivity_from_text
from app.services.trust_audit_constants import SAFETY_ENFORCEMENT_PATH

logger = logging.getLogger(__name__)


class RequiresExplicitSensitiveSendConfirmation(Exception):
    """Sensitive-looking local material would be sent off-machine without explicit confirmation."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message
            or "You are attempting to send sensitive local data externally. "
            "Confirm explicitly before Nexa sends this off your machine."
        )


@dataclass
class ExecutionContext:
    """Trust boundary for deriving instruction provenance — never trust raw LLM/JSON alone."""

    db: Session | None = None
    user_id: str | None = None
    trusted_instruction_source: str | None = None
    boundary: str = "unknown"
    user_confirmed_sensitive_send: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def derive_instruction_source(ctx: ExecutionContext) -> str:
    """
    Instruction provenance comes from trusted runtime context, not user-supplied payload fields.

    When ``trusted_instruction_source`` is set (chat / orchestrator boundary), use it.
    Otherwise use ``internal_system`` (workers, provider calls, robots.txt probes).
    """
    if ctx.trusted_instruction_source is not None:
        return normalize_instruction_source(ctx.trusted_instruction_source)
    return InstructionSource.INTERNAL_SYSTEM.value


def enforce_host_execution_policy(
    payload: dict[str, Any] | None,
    *,
    ctx: ExecutionContext | None = None,
    trusted_instruction_source: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    """
    Policy + provenance gates for host executor payloads (layers 1–2).

    Prefer passing ``ExecutionContext``; ``trusted_instruction_source`` / ``boundary``
    override context fields when provided for backward compatibility.
    """
    src = trusted_instruction_source
    b = boundary or "host"
    if ctx is not None:
        src = trusted_instruction_source if trusted_instruction_source is not None else ctx.trusted_instruction_source
        b = boundary or ctx.boundary
    return enforce_nexa_privileged_policy(payload, trusted_instruction_source=src, boundary=b)


def maybe_raise_sensitive_external_confirmation(
    body_preview: str | None,
    target_url: str,
    *,
    ctx: ExecutionContext | None = None,
) -> None:
    """
    Combined escalation: high-sensitivity content + outbound send requires explicit confirmation when configured.

    Uses the same sensitivity tier as ``sensitivity.detect_sensitivity_from_text`` to avoid drift.
    """
    s = get_settings()
    if not getattr(s, "nexa_sensitive_external_confirmation_required", False):
        return
    confirmed = bool(ctx.user_confirmed_sensitive_send if ctx else False)
    if confirmed:
        return
    if not (target_url or "").strip().lower().startswith(("http://", "https://")):
        return
    level: SensitivityLevel = detect_sensitivity_from_text(body_preview or "")
    if level != "high":
        return
    raise RequiresExplicitSensitiveSendConfirmation(
        "Sending sensitive local data externally requires explicit approval."
    )


def audit_execution_envelope(
    db: Session | None,
    *,
    event_type: str,
    ctx: ExecutionContext | None,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Structured audit row for post-mortem reconstruction."""
    if db is None:
        logger.debug("audit_execution_envelope skipped (no db) event=%s", event_type)
        return
    md: dict[str, Any] = {**policy_audit_metadata()}
    if ctx:
        md["boundary"] = ctx.boundary
        md["instruction_source_derived"] = derive_instruction_source(ctx)
        if ctx.user_id:
            md["context_user_id"] = str(ctx.user_id)[:64]
    if extra:
        md.update(extra)
    try:
        audit(
            db,
            event_type=event_type[:64],
            actor="enforcement_pipeline",
            user_id=str(ctx.user_id).strip()[:64] if ctx and ctx.user_id else None,
            message=(message or "")[:4000],
            metadata=md,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("audit_execution_envelope failed: %s", exc)


def audit_enforcement_path_if_enabled(
    db: Session | None,
    *,
    boundary: str,
    action_type: str,
    user_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    Optional DB row for post-mortem: which boundary applied enforcement (off by default; can be noisy).
    """
    if db is None:
        return
    s = get_settings()
    if not bool(getattr(s, "nexa_audit_enforcement_paths", False)):
        return
    md: dict[str, Any] = {**policy_audit_metadata(), "boundary": boundary, "action_type": action_type}
    if extra:
        md.update(extra)
    try:
        audit(
            db,
            event_type=SAFETY_ENFORCEMENT_PATH,
            actor="enforcement_pipeline",
            user_id=(str(user_id).strip()[:64] if (user_id or "").strip() else None),
            message=f"boundary={boundary} action={action_type}"[:4000],
            metadata=md,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("audit_enforcement_path_if_enabled failed: %s", exc)


def enforce_user_http_get_preflight(
    *,
    hostname: str,
    db: Session | None,
    owner_user_id: str | None,
    log_hint: str,
    settings: Any | None = None,
    workflow_id: str | None = None,
    run_id: str | None = None,
    execution_id: str | None = None,
) -> str | None:
    """
    Layer: permissions + egress policy for user-initiated HTTP GET.

    Returns error string to surface to caller, or None when allowed to proceed.
    """
    hn_chk = (hostname or "").strip().lower()
    if not hn_chk:
        return None
    s = settings if settings is not None else get_settings()
    if (
        getattr(s, "nexa_network_external_send_enforced", False)
        and db is not None
        and (owner_user_id or "").strip()
    ):
        from app.services.access_permissions import check_network_external_send_permission

        ok_ns, err_ns = check_network_external_send_permission(
            db, str(owner_user_id).strip(), hostname=hn_chk
        )
        if not ok_ns:
            logger.info("pipeline http_get egress denied host=%s hint=%s err=%s", hn_chk, log_hint, err_ns)
            try:
                from app.services.audit_service import audit
                from app.services.trust_audit_constants import NETWORK_EXTERNAL_SEND_BLOCKED
                from app.services.trust_audit_correlation import TrustCorrelation, merge_correlation

                corr = TrustCorrelation(
                    workflow_id=workflow_id,
                    run_id=run_id,
                    execution_id=execution_id,
                ).as_metadata()
                audit(
                    db,
                    event_type=NETWORK_EXTERNAL_SEND_BLOCKED,
                    actor="enforcement_pipeline",
                    user_id=str(owner_user_id).strip()[:64],
                    message=f"GET blocked hostname={hn_chk}"[:4000],
                    metadata=merge_correlation(
                        {
                            "hostname": hn_chk,
                            "reason": (err_ns or "external network egress denied")[:800],
                            "method": "GET",
                            "log_hint": (log_hint or "")[:200],
                        },
                        corr,
                    ),
                    workflow_id=workflow_id,
                    run_id=run_id,
                    execution_id=execution_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.info("trust audit network blocked skipped: %s", exc)
            return (err_ns or "external network egress denied")[:800]
    return None

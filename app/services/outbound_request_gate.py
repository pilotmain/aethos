# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Single choke point for outbound HTTP bodies — secret detection + optional hard block.

Invariant (extend as product surfaces grow):

    Any outbound HTTP request whose body carries user-written or model-derived content
    must pass through ``gate_outbound_http_body`` (or a wrapper that calls it), so secret
    heuristics and optional hard blocks cannot be skipped at new call sites.

GET requests without a sensitive body typically skip heavy checks; POST/JSON bodies run here.
Provider-only traffic that only carries provider API keys may skip this gate when those keys
would false-positive — document each exception next to the HTTP call.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.audit_service import audit
from app.services.secret_egress_gate import assert_safe_for_external_send
from app.services.sensitivity import detect_sensitivity_from_text
from app.services.trust_audit_constants import ACCESS_SENSITIVE_EGRESS_WARNING

logger = logging.getLogger(__name__)


def gate_outbound_http_body(
    body_text: str | None,
    *,
    url: str,
    method: str,
    db: Session | None = None,
    owner_user_id: str | None = None,
    instruction_source: str = "system",
) -> None:
    """
    Always evaluate secret-like content before off-machine sends.

    - Always logs a warning when the body may contain secrets.
    - When ``nexa_secret_egress_enforced`` is true, raises unless the body is clean.
    """
    s = get_settings()
    enforced = bool(getattr(s, "nexa_secret_egress_enforced", False))
    sensitivity_level = detect_sensitivity_from_text(body_text or "")
    if sensitivity_level == "none":
        return
    logger.warning(
        "outbound_body_gate: possible secrets in %s %s (instruction_source=%s)",
        (method or "").upper(),
        (url or "")[:160],
        instruction_source,
    )
    if db is not None and (owner_user_id or "").strip():
        try:
            audit(
                db,
                event_type=ACCESS_SENSITIVE_EGRESS_WARNING,
                actor="system",
                user_id=str(owner_user_id).strip(),
                message=f"{method} {url[:200]}",
                metadata={
                    "instruction_source": instruction_source,
                    "external_target": (url or "")[:800],
                    "data_sensitivity_flag": True,
                    "sensitivity_level": sensitivity_level,
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("sensitive_egress audit skipped: %s", exc)
    if enforced:
        assert_safe_for_external_send(
            body_text or "",
            allow_when=False,
            detail="Blocked: outbound payload may contain secrets or credentials.",
        )

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 2 — operator-facing privacy API (``/api/v1/privacy/*``)."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.privacy.llm_privacy_gate import evaluate_text_egress
from app.privacy.pii_detection import detect_pii
from app.privacy.pii_redaction import redact_text
from app.privacy.privacy_audit import privacy_logs_dir
from app.privacy.privacy_events import PrivacyEventType, emit_privacy_event
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_snapshot import build_mission_control_privacy_panel

router = APIRouter(tags=["privacy"])


class ScanBody(BaseModel):
    text: str = Field(..., max_length=500_000)


class RedactBody(BaseModel):
    text: str = Field(..., max_length=500_000)


class EvaluateEgressBody(BaseModel):
    text: str = Field(..., max_length=500_000)
    boundary: str = Field(default="http", max_length=64)


@router.get("/privacy/status")
def privacy_status() -> dict[str, Any]:
    """Public snapshot of privacy flags (no secrets)."""
    return build_mission_control_privacy_panel()


@router.get("/privacy/policy")
def privacy_policy() -> dict[str, Any]:
    s = get_settings()
    return {
        "allowed_modes": [m.value for m in PrivacyMode],
        "current_mode": getattr(s, "aethos_privacy_mode", "observe"),
        "notes": (
            "Changing mode requires setting AETHOS_PRIVACY_MODE (and related AETHOS_* flags) "
            "in the environment and restarting the API process."
        ),
    }


@router.get("/privacy/audit")
def privacy_audit(
    limit: int = 100,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Tail of ``~/.aethos/logs/privacy.log`` as parsed JSON lines (newest last)."""
    lim = max(1, min(int(limit), 500))
    path = privacy_logs_dir() / "privacy.log"
    if not path.is_file():
        return {"events": [], "path": str(path)}
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = lines[-lim:]
    events: list[Any] = []
    for ln in tail:
        ln = ln.strip()
        if not ln:
            continue
        try:
            events.append(json.loads(ln))
        except json.JSONDecodeError:
            events.append({"raw": ln[:500]})
    return {"events": events, "path": str(path)}


@router.post("/privacy/scan")
def privacy_scan(
    body: ScanBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Run deterministic PII detection on provided text (authenticated)."""
    matches = detect_pii(body.text)
    cats = sorted({m.category for m in matches})
    emit_privacy_event(
        PrivacyEventType.PII_DETECTED,
        details={"categories": cats, "count": len(matches), "source": "api_scan"},
    )
    return {
        "count": len(matches),
        "categories": cats,
        "matches": [m.as_public_dict() for m in matches],
    }


@router.post("/privacy/redact")
def privacy_redact(
    body: RedactBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Deterministic redaction of ``body.text`` (authenticated; no raw secret echo)."""
    matches = detect_pii(body.text)
    out = redact_text(body.text, matches)
    cats = sorted({m.category for m in matches})
    emit_privacy_event(
        PrivacyEventType.PII_REDACTED,
        details={"source": "api_redact", "count": len(matches), "categories": cats},
    )
    return {
        "redacted_text": out,
        "count": len(matches),
        "categories": cats,
    }


@router.post("/privacy/evaluate-egress")
def privacy_evaluate_egress_route(
    body: EvaluateEgressBody,
    _: str = Depends(get_valid_web_user_id),
) -> dict[str, Any]:
    """Structured egress evaluation for arbitrary text (parity with privacy gate policy)."""
    return evaluate_text_egress(body.text, boundary=body.boundary or "http")

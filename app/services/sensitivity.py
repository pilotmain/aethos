"""
Single source of truth for payload / text sensitivity tier (avoid recompute drift).

Levels are intentionally small: ``high`` means treat as secret-bearing for egress and audit;
other tiers are reserved for future heuristics without breaking call sites.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from app.services.secret_egress_gate import looks_like_secret_material

SensitivityLevel = Literal["high", "medium", "low", "none"]

# Reserved on privileged execution payloads — stamped at policy enforcement, not user-trusted.
NEXA_SENSITIVITY_KEY = "_nexa_sensitivity"

_POLICY_STAMP_KEYS = frozenset(
    {
        "nexa_safety_policy_version",
        "nexa_safety_policy_sha256",
        "nexa_safety_policy_version_int",
    }
)


def detect_sensitivity_from_text(text: str) -> SensitivityLevel:
    if looks_like_secret_material(text or ""):
        return "high"
    return "none"


def _payload_blob_for_sensitivity(payload: dict[str, Any] | None) -> str:
    p = dict(payload or {})
    for k in _POLICY_STAMP_KEYS:
        p.pop(k, None)
    p.pop(NEXA_SENSITIVITY_KEY, None)
    try:
        return json.dumps(p, sort_keys=True, default=str)[:500_000]
    except (TypeError, ValueError):
        return ""


def detect_sensitivity(payload: dict[str, Any] | None) -> SensitivityLevel:
    """Derive tier from executable payload fields (policy stamp keys excluded)."""
    return detect_sensitivity_from_text(_payload_blob_for_sensitivity(payload))


def stamp_payload_sensitivity(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp ``NEXA_SENSITIVITY_KEY`` from current content — call after policy stamps, before verify."""
    out = dict(payload or {})
    out[NEXA_SENSITIVITY_KEY] = detect_sensitivity(out)
    return out


def sensitivity_is_high(payload: dict[str, Any] | None) -> bool:
    raw = (payload or {}).get(NEXA_SENSITIVITY_KEY)
    if raw == "high":
        return True
    return detect_sensitivity(payload) == "high"

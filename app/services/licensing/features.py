"""Named commercial tier features — OSS core ignores these unless a valid license is loaded."""

from __future__ import annotations

import time
from typing import FrozenSet

from app.core.config import get_settings

from app.services.licensing.verify import verify_license_token

# Stable identifiers for signed license payloads (commercial builds).
FEATURE_SANDBOX_ADVANCED = "sandbox_advanced"
FEATURE_CREDENTIAL_VAULT_OS = "credential_vault_os"
FEATURE_SKILL_SCANNER = "skill_security_scanner"
FEATURE_ROUTING_COST_OPT = "routing_cost_optimization"
FEATURE_MEMORY_GRAPH = "memory_graph"
FEATURE_VOICE_RUNTIME = "voice_runtime"
FEATURE_WORKFLOW_PRO = "workflow_pro"

_COMMERCIAL_FEATURES: FrozenSet[str] = frozenset(
    {
        FEATURE_SANDBOX_ADVANCED,
        FEATURE_CREDENTIAL_VAULT_OS,
        FEATURE_SKILL_SCANNER,
        FEATURE_ROUTING_COST_OPT,
        FEATURE_MEMORY_GRAPH,
        FEATURE_VOICE_RUNTIME,
        FEATURE_WORKFLOW_PRO,
    }
)


def _parsed_license_payload() -> dict | None:
    s = get_settings()
    raw = (getattr(s, "nexa_license_key", None) or "").strip()
    pem = getattr(s, "nexa_license_public_key_pem", None)
    return verify_license_token(raw, public_key_pem=pem)


def has_pro_feature(feature: str) -> bool:
    """
    True when the configured license verifies and grants ``feature``.

    Wildcard ``*`` in payload ``features`` grants all known commercial feature IDs.
    """
    fid = (feature or "").strip()
    if fid not in _COMMERCIAL_FEATURES and fid != "*":
        return False
    payload = _parsed_license_payload()
    if not payload:
        return False
    exp = payload.get("exp")
    if exp is not None:
        try:
            if float(exp) < time.time():
                return False
        except (TypeError, ValueError):
            return False
    feats = payload.get("features")
    if not isinstance(feats, list):
        return False
    norm = {str(x).strip() for x in feats if str(x).strip()}
    if "*" in norm:
        return fid in _COMMERCIAL_FEATURES or fid == "*"
    return fid in norm


def licensed_feature_ids() -> frozenset[str]:
    """Resolved feature IDs from the current license (empty if none)."""
    payload = _parsed_license_payload()
    if not payload:
        return frozenset()
    feats = payload.get("features")
    if not isinstance(feats, list):
        return frozenset()
    return frozenset(str(x).strip() for x in feats if str(x).strip())


__all__ = [
    "FEATURE_CREDENTIAL_VAULT_OS",
    "FEATURE_MEMORY_GRAPH",
    "FEATURE_ROUTING_COST_OPT",
    "FEATURE_SANDBOX_ADVANCED",
    "FEATURE_SKILL_SCANNER",
    "FEATURE_VOICE_RUNTIME",
    "FEATURE_WORKFLOW_PRO",
    "has_pro_feature",
    "licensed_feature_ids",
]

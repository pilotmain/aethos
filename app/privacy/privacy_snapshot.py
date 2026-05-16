# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control — compact Phase 2 privacy panel (settings-derived; no secrets)."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def build_mission_control_privacy_panel() -> dict[str, Any]:
    s = get_settings()
    return {
        "privacy_mode": getattr(s, "aethos_privacy_mode", "observe"),
        "privacy_audit_enabled": bool(getattr(s, "aethos_privacy_audit_enabled", True)),
        "pii_redaction_enabled": bool(getattr(s, "aethos_pii_redaction_enabled", False)),
        "local_first_enabled": bool(getattr(s, "aethos_local_first_enabled", False)),
        "external_egress_guard_enabled": bool(getattr(s, "aethos_external_egress_guard_enabled", False)),
        "require_local_model": bool(getattr(s, "aethos_require_local_model", False)),
        "local_model_provider": getattr(s, "aethos_local_model_provider", "ollama"),
        "local_model_name_set": bool((getattr(s, "aethos_local_model_name", "") or "").strip()),
        "allow_external_fallback": bool(getattr(s, "aethos_allow_external_fallback", True)),
        "encryption_at_rest_enabled": bool(getattr(s, "aethos_encryption_at_rest_enabled", False)),
        "encryption_key_source": getattr(s, "aethos_encryption_key_source", "env"),
    }

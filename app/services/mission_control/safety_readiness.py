"""Aggregate safety / readiness signals for Mission Control."""

from __future__ import annotations

import shutil
from typing import Any

from app.core.config import get_settings

from app.services.network_policy.policy import recent_egress_attempts
from app.services.skills.manifest_registry import SkillPackageRegistry


def build_safety_readiness_snapshot(*, user_id: str | None = None) -> dict[str, Any]:
    s = get_settings()
    uid = (user_id or "")[:64]
    pkgs = SkillPackageRegistry().list_skills()
    blocked_recent = sum(
        1 for e in recent_egress_attempts(limit=50) if not e.get("allowed") and e.get("user_id") in (uid, "", None)
    )
    docker_ok = shutil.which("docker") is not None
    return {
        "execution_truth_guard_enabled": bool(getattr(s, "nexa_execution_truth_guard_enabled", True)),
        "execution_truth_policy": (
            "Assistant text does not prove live cloud changes unless a recorded tool run or "
            "dev mission completed with verification."
        ),
        "sandbox_mode": str(getattr(s, "nexa_sandbox_mode", "process") or "process"),
        "sandbox_docker_available": docker_ok,
        "credential_vault_provider": str(getattr(s, "nexa_credential_vault_provider", "local") or "local"),
        "network_egress_mode": str(getattr(s, "nexa_network_egress_mode", "allowlist") or "allowlist"),
        "network_egress_recent_blocked": blocked_recent,
        "token_budget_per_request": int(getattr(s, "nexa_token_budget_per_request", 8000) or 8000),
        "block_over_token_budget": bool(getattr(s, "nexa_block_over_token_budget", True)),
        "strict_privacy_mode": bool(getattr(s, "nexa_strict_privacy_mode", False)),
        "local_first": bool(getattr(s, "nexa_local_first", False)),
        "voice_enabled": bool(getattr(s, "nexa_voice_enabled", False)),
        "voice_transcribe_provider": str(getattr(s, "nexa_voice_transcribe_provider", "local") or "local"),
        "skill_package_count": len(pkgs),
        "user_id": uid or None,
        "install_hint": "Run ./scripts/install_check.sh or ./scripts/nexa_doctor.sh from the repo root.",
    }


__all__ = ["build_safety_readiness_snapshot"]

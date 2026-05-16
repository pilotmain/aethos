# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup completeness status (Phase 4 Step 10)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def build_setup_status(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    env_path = root / ".env"
    home_env = Path.home() / ".aethos" / ".env"
    profile = Path.home() / ".aethos" / "onboarding_profile.json"
    checks = {
        "env_file": env_path.is_file() or home_env.is_file(),
        "api_url": bool(os.environ.get("AETHOS_API_URL") or os.environ.get("NEXA_API_URL")),
        "bearer_token": bool(os.environ.get("AETHOS_API_BEARER") or os.environ.get("NEXA_API_BEARER")),
        "user_id": bool(os.environ.get("AETHOS_USER_ID") or os.environ.get("NEXA_USER_ID")),
        "onboarding_profile": profile.is_file(),
        "routing_mode": bool(os.environ.get("AETHOS_ROUTING_MODE") or os.environ.get("NEXA_ROUTING_MODE")),
    }
    passed = sum(1 for v in checks.values() if v)
    return {
        "complete": passed >= max(4, len(checks) - 2),
        "checks": checks,
        "passed": passed,
        "total": len(checks),
        "setup_modes": ["local-only", "cloud-only", "hybrid", "later"],
        "enterprise_installer": True,
        "bounded": True,
    }

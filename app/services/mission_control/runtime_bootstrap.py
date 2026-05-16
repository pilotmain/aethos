# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime bootstrap payload for Mission Control (Phase 4 Step 16)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.mission_control.runtime_api_capabilities import MC_COMPATIBILITY_VERSION


def _bootstrap_file() -> Path:
    return Path.home() / ".aethos" / "mc_browser_bootstrap.json"


def load_browser_bootstrap() -> dict[str, Any]:
    path = _bootstrap_file()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def build_runtime_bootstrap(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    file_boot = load_browser_bootstrap()
    api = (
        file_boot.get("apiBase")
        or os.environ.get("AETHOS_API_URL")
        or os.environ.get("NEXA_API_BASE")
        or "http://127.0.0.1:8000"
    )
    uid = file_boot.get("userId") or os.environ.get("AETHOS_USER_ID") or os.environ.get("TEST_X_USER_ID") or ""
    return {
        "runtime_bootstrap": {
            "api_base": api.rstrip("/") if isinstance(api, str) else api,
            "user_id": uid,
            "mc_compatibility_version": MC_COMPATIBILITY_VERSION,
            "connection_profile": os.environ.get("AETHOS_CONNECTION_PROFILE") or "default",
            "trust_seeded": bool(file_boot.get("trustSeeded") or uid),
            "onboarding_profile_present": (Path.home() / ".aethos" / "onboarding_profile.json").is_file(),
            "web_env_local": (root / "web" / ".env.local").is_file(),
            "browser_bootstrap_file": str(_bootstrap_file()),
            "seamless_localhost": True,
            "bounded": True,
        },
        "browser_bootstrap": file_boot,
    }


def write_browser_bootstrap(*, api_base: str, user_id: str, bearer_hint: str | None = None) -> Path:
    path = _bootstrap_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "apiBase": api_base.rstrip("/"),
        "userId": user_id,
        "mcCompatibilityVersion": MC_COMPATIBILITY_VERSION,
        "trustSeeded": True,
        "bearerConfigured": bool(bearer_hint),
    }
    path.write_text(json.dumps(blob, indent=2), encoding="utf-8")
    return path

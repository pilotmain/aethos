# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Env completeness audit helpers (Phase 4 Step 11)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Keys the enterprise setup wizard seeds or documents (AETHOS_* preferred; NEXA_* aliases allowed).
SETUP_COVERED_KEYS: frozenset[str] = frozenset(
    {
        "API_BASE_URL",
        "NEXA_API_BASE",
        "NEXA_WEB_API_TOKEN",
        "TEST_X_USER_ID",
        "X_USER_ID",
        "AETHOS_MISSION_CONTROL_URL",
        "AETHOS_CONNECTION_PROFILE",
        "AETHOS_ROUTING_MODE",
        "AETHOS_ROUTING_PREFERENCE",
        "AETHOS_ROUTING_REQUIRE_PAID_APPROVAL",
        "AETHOS_LOCAL_FIRST",
        "AETHOS_LOCAL_ONLY",
        "NEXA_LLM_PROVIDER",
        "NEXA_OLLAMA_ENABLED",
        "NEXA_WEB_ORIGINS",
        "AETHOS_TRUTH_CACHE_TTL_SEC",
        "AETHOS_TRUTH_SLICE_TTL_SEC",
        "NEXA_PRIVACY_MODE",
        "NEXA_TELEGRAM_BOT_TOKEN",
        "NEXA_WEB_SEARCH_PROVIDER",
        "NEXA_WEB_SEARCH_API_KEY",
        "NEXA_WORKSPACE_ROOT",
    }
)

COMPATIBILITY_ALIASES: dict[str, str] = {
    "NEXA_API_BASE": "API_BASE_URL / AETHOS_API_URL",
    "NEXA_WEB_API_TOKEN": "AETHOS_API_BEARER (legacy name)",
    "TEST_X_USER_ID": "Mission Control dev user id",
    "NEXA_ROUTING_MODE": "AETHOS_ROUTING_MODE",
}


def _parse_env_example(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def build_env_completeness_audit(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    example_keys = _parse_env_example(root / ".env.example")
    setup_covered = sorted(SETUP_COVERED_KEYS)
    optional_in_example = sorted(example_keys - SETUP_COVERED_KEYS)[:80]
    missing_from_setup = sorted(
        k
        for k in (
            "NEXA_SECRET_KEY",
            "NEXA_WEB_ORIGINS",
            "AETHOS_RUNTIME_EVENT_BUFFER_LIMIT",
        )
        if k in example_keys and k not in SETUP_COVERED_KEYS
    )
    return {
        "required_categories": [
            "runtime",
            "auth_mission_control",
            "providers_brains",
            "privacy",
            "channels",
            "web_search",
            "runtime_performance",
        ],
        "setup_covered_keys": setup_covered,
        "setup_covered_count": len(setup_covered),
        "env_example_key_count": len(example_keys),
        "compatibility_aliases": COMPATIBILITY_ALIASES,
        "manual_only_keys": missing_from_setup,
        "optional_sample": optional_in_example[:40],
        "bounded": True,
    }

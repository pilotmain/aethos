# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Capability flags per brain provider (Phase 2 Step 7)."""

from __future__ import annotations

from typing import Any

REPAIR_PLAN_TASK = "repair_plan"

_CAPABILITIES: dict[str, dict[str, Any]] = {
    "deterministic": {
        "repair_plan": True,
        "structured_json": True,
        "local": True,
        "external_egress": False,
    },
    "ollama": {
        "repair_plan": True,
        "structured_json": True,
        "local": True,
        "external_egress": False,
    },
    "local_stub": {
        "repair_plan": True,
        "structured_json": True,
        "local": True,
        "external_egress": False,
    },
    "openai": {
        "repair_plan": True,
        "structured_json": True,
        "local": False,
        "external_egress": True,
    },
    "anthropic": {
        "repair_plan": True,
        "structured_json": True,
        "local": False,
        "external_egress": True,
    },
}


def brain_supports_task(provider: str, task: str) -> bool:
    caps = _CAPABILITIES.get((provider or "").strip().lower(), {})
    return bool(caps.get(task))


def brain_is_local(provider: str) -> bool:
    caps = _CAPABILITIES.get((provider or "").strip().lower(), {})
    return bool(caps.get("local"))


def describe_brain(provider: str) -> dict[str, Any]:
    key = (provider or "").strip().lower() or "unknown"
    return {"provider": key, **(_CAPABILITIES.get(key) or {})}

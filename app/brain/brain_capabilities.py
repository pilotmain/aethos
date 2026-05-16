# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Capability flags per brain provider (Phase 2 Step 7)."""

from __future__ import annotations

from typing import Any

REPAIR_PLAN_TASK = "repair_plan"

BRAIN_TASKS = frozenset(
    {
        "repair_planning",
        "deployment_diagnosis",
        "workflow_planning",
        "summarization",
        "code_editing",
        "research",
        "debugging",
        "analysis",
        REPAIR_PLAN_TASK,
    }
)

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


def score_brain_for_task(provider: str, task: str, *, local_first: bool = False) -> float:
    """Lightweight capability + policy scoring for routing transparency."""
    caps = _CAPABILITIES.get((provider or "").strip().lower(), {})
    score = 0.0
    if caps.get(task) or caps.get("repair_plan"):
        score += 0.5
    if local_first and caps.get("local"):
        score += 0.35
    if not caps.get("external_egress"):
        score += 0.1
    return round(min(1.0, score), 3)


def fallback_chain_for_task(task: str, candidates: list[dict[str, Any]]) -> list[str]:
    chain = []
    for row in candidates:
        p = str(row.get("provider") or "")
        if p and brain_supports_task(p, task if task in BRAIN_TASKS else REPAIR_PLAN_TASK):
            chain.append(p)
    if "deterministic" not in chain:
        chain.append("deterministic")
    return chain

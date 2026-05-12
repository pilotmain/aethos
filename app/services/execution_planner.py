# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Extended NL matching and multi-step *workspace file* plans (no shell from gateway)."""

from __future__ import annotations

import re
from threading import Lock
from typing import Any

_EXTENDED_BUILD = re.compile(
    r"^(?P<verb>build|create|make)\s+(?:a|an)\s+(?P<tail>.+?)\s*$",
    re.IGNORECASE,
)

_DB_HINT = re.compile(
    r"\b(database|db|postgres|mysql|sqlite|sql|backend|api)\b",
    re.IGNORECASE,
)

_DEPLOY_HINT = re.compile(r"^\s*(deploy|publish|go live)\b", re.IGNORECASE)

_active_lock = Lock()
_active_by_user: dict[str, int] = {}


def parse_extended_build_intent(text: str) -> dict[str, Any] | None:
    """
    Broad ``build/create/make a …`` line (multi-word tail) when execution planner is enabled.

    Returns a dict compatible with :func:`goal_orchestrator.parse_goal_intent` consumers
    (``intent_type``, ``groups``, ``line``) plus ``hints``.
    """
    raw = (text or "").strip()
    if not raw:
        return None
    line = raw.splitlines()[0].strip()
    if _DEPLOY_HINT.search(line):
        return None
    if len(line.split()) < 4:
        return None
    m = _EXTENDED_BUILD.match(line)
    if not m:
        return None
    tail = (m.group("tail") or "").strip()
    if not tail or len(tail) < 3:
        return None
    hints = {"want_db": bool(_DB_HINT.search(line))}
    return {
        "intent_type": "goal_build_multi",
        "groups": (tail,),
        "line": line,
        "hints": hints,
    }


def build_multi_step_specs(hints: dict[str, Any], tail: str) -> list[dict[str, Any]]:
    """Ordered step specs → converted to ``SubGoal`` in :mod:`goal_orchestrator`."""
    from app.services.execution_templates import slugify_phrase, todo_backend_node_bundle, todo_static_bundle

    slug = slugify_phrase(tail)
    specs: list[dict[str, Any]] = [
        {
            "id": "sg1",
            "description": f"Scaffold static UI for `{slug}`",
            "step_kind": "batch_files",
            "meta": {"files": todo_static_bundle(slug)},
        }
    ]
    if hints.get("want_db"):
        specs.append(
            {
                "id": "sg2",
                "description": "Add minimal Node JSON-file backend (no npm in-plan)",
                "step_kind": "batch_files",
                "meta": {"files": todo_backend_node_bundle(slug)},
            }
        )
    return specs


def acquire_plan_slot(user_id: str, max_concurrent: int) -> bool:
    if max_concurrent < 1:
        max_concurrent = 1
    with _active_lock:
        n = _active_by_user.get(user_id, 0)
        if n >= max_concurrent:
            return False
        _active_by_user[user_id] = n + 1
        return True


def release_plan_slot(user_id: str) -> None:
    with _active_lock:
        n = _active_by_user.get(user_id, 0)
        if n <= 1:
            _active_by_user.pop(user_id, None)
        else:
            _active_by_user[user_id] = n - 1


__all__ = [
    "acquire_plan_slot",
    "build_multi_step_specs",
    "parse_extended_build_intent",
    "release_plan_slot",
]

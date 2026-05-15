# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous NL goal decomposition and deterministic workspace execution."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.config import get_settings
from app.services.batch_executor import create_batch_files
from app.services.execution_templates import todo_static_bundle

_GOAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^build\s+(?:a|an)\s+(\w+)\s+app$", re.I), "goal_build_app"),
    (re.compile(r"^create\s+(?:a|an)\s+(\w+)\s+project$", re.I), "goal_create_project"),
    (re.compile(r"^deploy\s+(?:a|an)\s+(\w+)\s+to\s+(\w+)$", re.I), "goal_deploy"),
    (re.compile(r"^make\s+me\s+(?:a|an)\s+(\w+)$", re.I), "goal_create"),
]


class GoalStatus(Enum):
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass
class SubGoal:
    id: str
    description: str
    assigned_agent: str
    dependencies: list[str]
    status: GoalStatus
    result: Any = None
    step_kind: str = "generic"
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    id: str
    user_intent: str
    sub_goals: list[SubGoal]
    status: GoalStatus
    created_at: datetime
    intent_type: str = ""
    completed_at: datetime | None = None


def parse_goal_intent(text: str) -> dict[str, Any] | None:
    """Match first line against autonomous goal patterns."""
    if bool(getattr(get_settings(), "nexa_llm_first_gateway", False)):
        return None
    raw = (text or "").strip()
    if not raw:
        return None
    line = raw.splitlines()[0].strip()
    for rx, name in _GOAL_PATTERNS:
        m = rx.match(line)
        if not m:
            continue
        groups = m.groups()
        return {"intent_type": name, "groups": groups, "line": line}
    if bool(getattr(get_settings(), "nexa_execution_planner_enabled", False)):
        from app.services.execution_planner import parse_extended_build_intent

        ext = parse_extended_build_intent(raw)
        if ext:
            return ext
    return None


def is_goal_planning_line(text: str) -> bool:
    """True when ``text`` matches a deterministic autonomous goal (avoids dev auto-confirm gate)."""
    return parse_goal_intent(text) is not None


def _todo_app_files(slug: str) -> list[dict[str, Any]]:
    return list(todo_static_bundle(slug))


class GoalOrchestrator:
    """Deterministic planning + execution (no LLM required for MVP)."""

    def plan_sync(self, parsed: dict[str, Any], user_input: str) -> Goal:
        intent = str(parsed.get("intent_type") or "")
        groups = tuple(parsed.get("groups") or ())
        gid = str(uuid.uuid4())[:12]
        subs: list[SubGoal] = []
        if intent == "goal_build_app":
            slug = str(groups[0] if groups else "app")
            subs.append(
                SubGoal(
                    id="sg1",
                    description=f"Scaffold static files for `{slug}` app",
                    assigned_agent="workspace",
                    dependencies=[],
                    status=GoalStatus.PLANNING,
                    step_kind="batch_files",
                    meta={"files": _todo_app_files(slug)},
                )
            )
        elif intent == "goal_build_multi":
            from app.services.execution_planner import build_multi_step_specs

            tail = str(groups[0] if groups else "app")
            hints = dict(parsed.get("hints") or {})
            for spec in build_multi_step_specs(hints, tail):
                subs.append(
                    SubGoal(
                        id=str(spec.get("id") or "sg"),
                        description=str(spec.get("description") or "step"),
                        assigned_agent="workspace",
                        dependencies=[],
                        status=GoalStatus.PLANNING,
                        step_kind=str(spec.get("step_kind") or "batch_files"),
                        meta=dict(spec.get("meta") or {}),
                    )
                )
        elif intent == "goal_create_project":
            slug = str(groups[0] if groups else "project")
            subs.append(
                SubGoal(
                    id="sg1",
                    description=f"Create minimal project README for `{slug}`",
                    assigned_agent="workspace",
                    dependencies=[],
                    status=GoalStatus.PLANNING,
                    step_kind="batch_files",
                    meta={
                        "files": [
                            {
                                "filename": f"{slug}/README.md",
                                "content": f"# {slug}\n\nCreated by autonomous goal planner.\n",
                            }
                        ]
                    },
                )
            )
        elif intent == "goal_deploy":
            target = str(groups[1] if len(groups) > 1 else "prod")
            svc = str(groups[0] if groups else "app")
            subs.append(
                SubGoal(
                    id="sg1",
                    description=f"Deploy `{svc}` to {target}",
                    assigned_agent="operator",
                    dependencies=[],
                    status=GoalStatus.PLANNING,
                    step_kind="deploy_stub",
                    meta={"service": svc, "target": target},
                )
            )
        elif intent == "goal_create":
            name = str(groups[0] if groups else "thing")
            subs.append(
                SubGoal(
                    id="sg1",
                    description=f"Create artifact `{name}`",
                    assigned_agent="workspace",
                    dependencies=[],
                    status=GoalStatus.PLANNING,
                    step_kind="batch_files",
                    meta={
                        "files": [
                            {"filename": f"{name}.txt", "content": f"Created: {name}\n"},
                        ]
                    },
                )
            )
        return Goal(
            id=gid,
            user_intent=user_input.strip(),
            sub_goals=subs,
            status=GoalStatus.PLANNING,
            created_at=datetime.now(UTC),
            intent_type=intent,
        )

    def execute_goal_sync(
        self,
        goal: Goal,
        *,
        workspace_root: str,
        owner_user_id: str,
    ) -> dict[str, Any]:
        goal.status = GoalStatus.IN_PROGRESS
        results: list[dict[str, Any]] = []
        ok_all = True
        for sg in goal.sub_goals:
            sg.status = GoalStatus.IN_PROGRESS
            if sg.step_kind == "batch_files":
                files = list(sg.meta.get("files") or [])
                out = create_batch_files(files, workspace_root, owner_user_id)
                sg.result = out
                sg.status = GoalStatus.COMPLETED if out.get("success") else GoalStatus.FAILED
                results.append({"sub_goal": sg.id, "result": out})
                if not out.get("success"):
                    ok_all = False
            elif sg.step_kind == "deploy_stub":
                msg = (
                    f"Deploy `{sg.meta.get('service')}` → `{sg.meta.get('target')}` "
                    "requires host executor / provider setup (not executed automatically)."
                )
                sg.result = {"success": True, "note": msg}
                sg.status = GoalStatus.COMPLETED
                results.append({"sub_goal": sg.id, "result": sg.result})
            else:
                sg.status = GoalStatus.FAILED
                sg.result = {"success": False, "error": "unknown step_kind"}
                results.append({"sub_goal": sg.id, "result": sg.result})
                ok_all = False
        goal.status = GoalStatus.COMPLETED if ok_all else GoalStatus.FAILED
        goal.completed_at = datetime.now(UTC)
        return {"goal_id": goal.id, "ok": ok_all, "results": results}


def format_goal_result(payload: dict[str, Any], goal: Goal) -> str:
    results = list(payload.get("results") or [])
    n = len(results)
    lines = [
        "## Autonomous goal",
        "",
        f"**Goal id:** `{payload.get('goal_id')}`",
        f"**Status:** {'completed' if payload.get('ok') else 'failed'}",
        "",
        f"### Steps ({n})",
        "",
    ]
    for i, r in enumerate(results, 1):
        res = r.get("result") or {}
        sg = r.get("sub_goal")
        lines.append(f"**Step {i}/{n}** — `{sg}` → `{res.get('success')}`")
        if res.get("note"):
            lines.append(f"  - {res['note']}")
        if res.get("count") is not None:
            lines.append(f"  - files written: {res.get('count')}")
        if res.get("files"):
            for f in res.get("files") or []:
                fn = f.get("filename") if isinstance(f, dict) else str(f)
                lines.append(f"    - `{fn}`")
        lines.append("")
    lines.append(f"_Intent:_ {goal.intent_type or 'unknown'}")
    return "\n".join(lines)


__all__ = [
    "Goal",
    "GoalOrchestrator",
    "GoalStatus",
    "SubGoal",
    "format_goal_result",
    "is_goal_planning_line",
    "parse_goal_intent",
]

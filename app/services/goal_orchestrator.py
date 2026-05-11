"""Autonomous NL goal decomposition and deterministic workspace execution."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.services.batch_executor import create_batch_files

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
    return None


def _todo_app_files(slug: str) -> list[dict[str, Any]]:
    safe = slug.lower().replace(" ", "-")[:48] or "app"
    base = f"{safe}-app"
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe} todo</title>
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main class="wrap">
    <h1>{safe} — todos</h1>
    <form id="add-form">
      <input id="task" type="text" placeholder="New task" autocomplete="off" />
      <button type="submit">Add</button>
    </form>
    <ul id="list"></ul>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""
    css = """body { font-family: system-ui, sans-serif; margin: 2rem; background: #0f172a; color: #e2e8f0; }
.wrap { max-width: 520px; margin: 0 auto; }
input { width: 70%; padding: 0.5rem; border-radius: 6px; border: 1px solid #334155; background: #020617; color: inherit; }
button { padding: 0.5rem 0.75rem; border-radius: 6px; border: 0; background: #38bdf8; color: #0f172a; cursor: pointer; }
ul { list-style: none; padding: 0; }
li { padding: 0.5rem 0; border-bottom: 1px solid #1e293b; display: flex; justify-content: space-between; gap: 0.5rem; }
.done { text-decoration: line-through; opacity: 0.6; }
"""
    js = """const form = document.getElementById("add-form");
const input = document.getElementById("task");
const list = document.getElementById("list");
const storageKey = "nexa-todo-items";
let items = [];
try { items = JSON.parse(localStorage.getItem(storageKey) || "[]"); } catch { items = []; }
function save() { localStorage.setItem(storageKey, JSON.stringify(items)); render(); }
function render() {
  list.innerHTML = "";
  items.forEach((text, i) => {
    const li = document.createElement("li");
    const span = document.createElement("span");
    span.textContent = text;
    span.className = "";
    const toggle = document.createElement("button");
    toggle.textContent = "Done";
    toggle.onclick = () => { items.splice(i, 1); save(); };
    li.appendChild(span);
    li.appendChild(toggle);
    list.appendChild(li);
  });
}
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const v = (input.value || "").trim();
  if (!v) return;
  items.push(v);
  input.value = "";
  save();
});
render();
"""
    readme = f"# {safe} todo\n\nOpen `index.html` in a browser (or serve statically).\n"
    return [
        {"filename": f"{base}/index.html", "content": html},
        {"filename": f"{base}/styles.css", "content": css},
        {"filename": f"{base}/app.js", "content": js},
        {"filename": f"{base}/README.md", "content": readme},
    ]


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
    lines = [
        "## Autonomous goal",
        "",
        f"**Goal id:** `{payload.get('goal_id')}`",
        f"**Status:** {'completed' if payload.get('ok') else 'failed'}",
        "",
        "### Steps",
        "",
    ]
    for r in payload.get("results") or []:
        res = r.get("result") or {}
        sg = r.get("sub_goal")
        lines.append(f"- **{sg}:** `{res.get('success')}`")
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
    "parse_goal_intent",
]

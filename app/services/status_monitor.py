# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""In-process task/status dashboard for Agentic OS UX (best-effort; single-worker scope)."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from app.core.config import get_settings


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TrackedTask:
    id: str
    name: str
    status: TaskStatus
    assigned_to: str
    owner_user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    progress: int = 0
    detail: str = ""


class StatusMonitor:
    """Singleton-style monitor (process-local)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tasks: dict[str, TrackedTask] = {}
        self.heartbeat = True
        self.active_agents: dict[str, str] = {}
        self._last_tick: float = time.time()

    def tick(self) -> None:
        self._last_tick = time.time()

    def register_active_agent(self, name: str, state: str = "active") -> None:
        self.active_agents[name] = state

    def start_long_task(
        self,
        owner_user_id: str,
        name: str,
        assigned_to: str = "host",
    ) -> str:
        uid = (owner_user_id or "").strip()[:64]
        max_tasks = max(1, int(getattr(get_settings(), "nexa_max_concurrent_tasks", 5)))
        tid = str(uuid.uuid4())[:12]
        with self._lock:
            in_flight = sum(
                1
                for t in self.tasks.values()
                if t.owner_user_id == uid
                and t.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
            )
            if in_flight >= max_tasks:
                raise RuntimeError(
                    f"Too many concurrent tasks ({max_tasks}); wait for one to finish."
                )
            self.tasks[tid] = TrackedTask(
                id=tid,
                name=name[:500],
                status=TaskStatus.IN_PROGRESS,
                assigned_to=assigned_to[:120],
                owner_user_id=uid,
                progress=0,
            )
        self.tick()
        return tid

    def update_task_progress(
        self,
        task_id: str,
        progress: int,
        status: TaskStatus,
        *,
        detail: str = "",
    ) -> None:
        with self._lock:
            t = self.tasks.get(task_id)
            if not t:
                return
            t.progress = max(0, min(100, int(progress)))
            t.status = status
            t.updated_at = datetime.now(timezone.utc)
            if detail:
                t.detail = detail[:2000]
        self.tick()

    def complete_task(self, task_id: str, *, ok: bool = True, detail: str = "") -> None:
        self.update_task_progress(
            task_id,
            100,
            TaskStatus.COMPLETED if ok else TaskStatus.FAILED,
            detail=detail,
        )

    def get_dashboard_markdown(self, owner_user_id: str) -> str:
        uid = (owner_user_id or "").strip()[:64]
        with self._lock:
            mine = [t for t in self.tasks.values() if t.owner_user_id == uid]
        lines: list[str] = ["## 📋 Status dashboard\n"]

        pending = [t for t in mine if t.status == TaskStatus.PENDING]
        if pending:
            lines.append(f"### ⏳ To do ({len(pending)})")
            for t in pending[:8]:
                lines.append(f"- {t.name} (@{t.assigned_to})")

        prog = [t for t in mine if t.status == TaskStatus.IN_PROGRESS]
        if prog:
            lines.append(f"\n### 🔄 In progress ({len(prog)})")
            for t in prog[:8]:
                bar_n = max(0, min(10, t.progress // 10))
                bar = "█" * bar_n + "░" * (10 - bar_n)
                lines.append(f"- {t.name} [{bar} {t.progress}%] — @{t.assigned_to}")
                if t.detail:
                    lines.append(f"  _{t.detail[:200]}_")

        done = [t for t in mine if t.status == TaskStatus.COMPLETED]
        if done:
            lines.append(f"\n### ✅ Completed ({len(done)})")
            for t in done[-6:]:
                lines.append(f"- {t.name}")

        failed = [t for t in mine if t.status == TaskStatus.FAILED]
        if failed:
            lines.append(f"\n### ❌ Failed ({len(failed)})")
            for t in failed[-4:]:
                lines.append(f"- {t.name}")

        active = [n for n, st in self.active_agents.items() if st == "active"]
        if active:
            lines.append(f"\n### 🤖 Active agents ({len(active)})")
            lines.append(", ".join(f"@{a}" for a in active[:24]))

        hb = "✅ Alive" if self.heartbeat else "❌ Down"
        lines.append(f"\n💓 Heartbeat: {hb}")
        return "\n".join(lines).strip()

    def format_who_is_working(self, owner_user_id: str) -> str:
        """Bold section for NL ``who is working`` — agents marked active in this process."""
        _ = owner_user_id
        with self._lock:
            pairs = [(n, st) for n, st in self.active_agents.items() if st == "active"]
        if not pairs:
            return "### 👤 Who is working\n\n_No registered agents marked active in this process._"
        body = "\n".join(f"- **@{n}** ({st})" for n, st in sorted(pairs, key=lambda x: x[0].lower())[:32])
        return f"### 👤 Who is working\n\n{body}"


_MONITOR = StatusMonitor()


def get_status_monitor() -> StatusMonitor:
    return _MONITOR


__all__ = [
    "StatusMonitor",
    "TaskStatus",
    "TrackedTask",
    "get_status_monitor",
]

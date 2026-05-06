"""
SQLite-backed audit trail for orchestration sub-agent actions (Phase 37).
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _json_dumps(obj: Any) -> str | None:
    if obj is None:
        return None
    try:
        return json.dumps(obj, default=str)
    except Exception:
        return json.dumps({"repr": repr(obj)})


def _json_loads(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


class AgentActivityTracker:
    """Persist agent actions for CEO dashboard and audit."""

    def __init__(self) -> None:
        settings = get_settings()
        root = Path(getattr(settings, "nexa_data_dir", "") or "data")
        self.db_path = root / "agent_audit.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS agent_actions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        agent_name TEXT,
                        action_type TEXT NOT NULL,
                        input TEXT,
                        output TEXT,
                        success INTEGER NOT NULL DEFAULT 1,
                        error TEXT,
                        duration_ms REAL,
                        metadata TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_actions_agent_id ON agent_actions(agent_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_actions_created_at ON agent_actions(created_at)")

    def log_action(
        self,
        *,
        agent_id: str,
        action_type: str,
        input_data: Any = None,
        output_data: Any = None,
        success: bool = True,
        error: str | None = None,
        duration_ms: float | None = None,
        metadata: dict[str, Any] | None = None,
        agent_name: str | None = None,
    ) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO agent_actions
                    (agent_id, agent_name, action_type, input, output, success, error, duration_ms, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        agent_id,
                        agent_name,
                        action_type,
                        _json_dumps(input_data),
                        _json_dumps(output_data),
                        1 if success else 0,
                        error,
                        duration_ms,
                        _json_dumps(metadata),
                    ),
                )

    def get_agent_history(
        self,
        agent_id: str,
        *,
        hours: int = 24,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT id, agent_id, agent_name, action_type, input, output, success, error,
                           duration_ms, metadata, created_at
                    FROM agent_actions
                    WHERE agent_id = ?
                      AND datetime(created_at) >= datetime('now', '-' || ? || ' hours')
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (agent_id, max(0, int(hours)), max(1, int(limit))),
                )
                rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_agent_statistics(self, agent_id: str, *, days: int = 30) -> dict[str, Any]:
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS successful,
                        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed,
                        AVG(duration_ms) AS avg_duration_ms
                    FROM agent_actions
                    WHERE agent_id = ?
                      AND datetime(created_at) >= datetime('now', '-' || ? || ' days')
                    """,
                    (agent_id, max(1, int(days))),
                )
                row = cur.fetchone()
        total = int(row["total"] or 0) if row else 0
        successful = int(row["successful"] or 0) if row else 0
        failed = int(row["failed"] or 0) if row else 0
        avg_ms = float(row["avg_duration_ms"] or 0.0) if row else 0.0
        rate = (successful / total * 100.0) if total > 0 else 100.0
        return {
            "total_actions": total,
            "successful_actions": successful,
            "failed_actions": failed,
            "success_rate": round(rate, 2),
            "avg_duration_ms": round(avg_ms, 2),
            # Aliases for dashboards
            "total_tasks": total,
        }

    def count_actions_today(self, agent_ids: list[str]) -> int:
        if not agent_ids:
            return 0
        placeholders = ",".join("?" * len(agent_ids))
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    f"""
                    SELECT COUNT(*) AS c FROM agent_actions
                    WHERE agent_id IN ({placeholders})
                      AND date(created_at) = date('now')
                    """,
                    tuple(agent_ids),
                )
                row = cur.fetchone()
        return int(row["c"] or 0) if row else 0

    def get_global_activity(
        self,
        agent_ids: list[str],
        *,
        hours: int = 24,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not agent_ids:
            return []
        placeholders = ",".join("?" * len(agent_ids))
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    f"""
                    SELECT id, agent_id, agent_name, action_type, input, output, success, error,
                           duration_ms, metadata, created_at
                    FROM agent_actions
                    WHERE agent_id IN ({placeholders})
                      AND datetime(created_at) >= datetime('now', '-' || ? || ' hours')
                    ORDER BY datetime(created_at) DESC
                    LIMIT ?
                    """,
                    (*agent_ids, max(0, int(hours)), max(1, int(limit))),
                )
                rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_agent_status_summary(self) -> dict[str, Any]:
        """Cross-agent rollup (all rows in DB)."""
        with self._lock:
            with self._connect() as conn:
                cur = conn.execute(
                    """
                    SELECT
                        agent_id,
                        MAX(agent_name) AS agent_name,
                        COUNT(*) AS total_actions,
                        AVG(CASE WHEN success = 1 THEN 1.0 ELSE 0.0 END) * 100 AS success_rate,
                        MAX(created_at) AS last_active
                    FROM agent_actions
                    GROUP BY agent_id
                    ORDER BY MAX(datetime(created_at)) DESC
                    """
                )
                rows = cur.fetchall()
        agents = [
            {
                "agent_id": r["agent_id"],
                "agent_name": r["agent_name"],
                "total_actions": int(r["total_actions"] or 0),
                "success_rate": round(float(r["success_rate"] or 0.0), 1),
                "last_active": r["last_active"],
            }
            for r in rows
        ]
        total_actions = sum(a["total_actions"] for a in agents)
        overall = 100.0
        if agents:
            # crude weighted average by action count
            w = sum(a["total_actions"] * (a["success_rate"] / 100.0) for a in agents)
            overall = round((w / total_actions) * 100.0, 1) if total_actions else 100.0
        return {"agents": agents, "total_actions": total_actions, "success_rate": overall}

    @staticmethod
    def _row_to_dict(r: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": r["id"],
            "agent_id": r["agent_id"],
            "agent_name": r["agent_name"],
            "action_type": r["action_type"],
            "input": _json_loads(r["input"]),
            "output": _json_loads(r["output"]),
            "success": bool(r["success"]),
            "error": r["error"],
            "duration_ms": float(r["duration_ms"]) if r["duration_ms"] is not None else None,
            "metadata": _json_loads(r["metadata"]),
            "created_at": r["created_at"],
        }


_activity_tracker: AgentActivityTracker | None = None


def get_activity_tracker() -> AgentActivityTracker:
    global _activity_tracker
    if _activity_tracker is None:
        _activity_tracker = AgentActivityTracker()
    return _activity_tracker


__all__ = ["AgentActivityTracker", "get_activity_tracker"]

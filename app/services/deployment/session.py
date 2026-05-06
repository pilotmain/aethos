"""
Deployment session tracking — remembers recent deploys per chat for autonomous status/logs.

SQLite store under ``data/deployment_sessions.sqlite`` (repo-root ``data/``).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class DeploymentSession:
    """Persist deployment sessions so ops agents can report status without re-asking."""

    def __init__(self, db_path: Path | None = None) -> None:
        root = Path(REPO_ROOT).resolve()
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or (data_dir / "deployment_sessions.sqlite")
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deployment_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    status TEXT,
                    url TEXT,
                    logs_url TEXT,
                    error_message TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    last_logs TEXT,
                    metadata TEXT
                )
                """
            )
            conn.row_factory = sqlite3.Row
            cur = conn.execute("PRAGMA table_info(deployment_sessions)")
            cols = {str(r[1]) for r in cur.fetchall()}
            if "error_message" not in cols:
                conn.execute("ALTER TABLE deployment_sessions ADD COLUMN error_message TEXT")

    def start_session(self, chat_id: str, platform: str, metadata: dict[str, Any] | None = None) -> int:
        cid = (chat_id or "").strip()
        plat = (platform or "").strip().lower() or "unknown"
        meta_json = json.dumps(metadata or {}, separators=(",", ":"))
        now = _utc_iso()
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                """
                INSERT INTO deployment_sessions (chat_id, platform, status, started_at, metadata)
                VALUES (?, ?, 'running', ?, ?)
                """,
                (cid, plat, now, meta_json),
            )
            return int(cur.lastrowid)

    def update_session(
        self,
        session_id: int,
        status: str,
        *,
        url: str | None = None,
        logs_url: str | None = None,
        error: str | None = None,
        set_completed: bool = True,
        clear_error: bool = False,
    ) -> None:
        """Update deployment row; optionally stamp ``completed_at``."""
        with sqlite3.connect(str(self.db_path)) as conn:
            row = conn.execute(
                "SELECT metadata FROM deployment_sessions WHERE id = ?", (session_id,)
            ).fetchone()
            meta: dict[str, Any] = {}
            if row and row[0]:
                try:
                    meta = json.loads(row[0])
                except json.JSONDecodeError:
                    meta = {}
            if error:
                meta["error"] = error[:4000]
            elif clear_error and "error" in meta:
                meta.pop("error", None)
            completed_val = _utc_iso() if set_completed else None
            err_sql = "error_message = error_message"
            err_bind: tuple[str, ...] = ()
            if clear_error:
                err_sql = "error_message = NULL"
            elif error is not None:
                err_sql = "error_message = ?"
                err_bind = ((error or "")[:8000],)

            conn.execute(
                f"""
                UPDATE deployment_sessions
                SET status = ?,
                    url = COALESCE(?, url),
                    logs_url = COALESCE(?, logs_url),
                    {err_sql},
                    completed_at = COALESCE(?, completed_at),
                    metadata = ?
                WHERE id = ?
                """,
                (
                    status,
                    url,
                    logs_url,
                    *err_bind,
                    completed_val,
                    json.dumps(meta, separators=(",", ":")),
                    session_id,
                ),
            )

    def get_last_session(self, chat_id: str, platform: str | None = None) -> dict[str, Any] | None:
        cid = (chat_id or "").strip()
        if not cid:
            return None
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            if platform:
                plat = platform.strip().lower()
                row = conn.execute(
                    """
                    SELECT * FROM deployment_sessions
                    WHERE chat_id = ? AND platform = ?
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (cid, plat),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT * FROM deployment_sessions
                    WHERE chat_id = ?
                    ORDER BY started_at DESC LIMIT 1
                    """,
                    (cid,),
                ).fetchone()
        if row is None:
            return None
        d = dict(row)
        raw_meta = d.get("metadata")
        try:
            d["metadata"] = json.loads(raw_meta) if raw_meta else {}
        except json.JSONDecodeError:
            d["metadata"] = {}
        return d

    def store_logs(self, session_id: int, logs: str) -> None:
        blob = (logs or "")[:10000]
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                UPDATE deployment_sessions SET last_logs = ? WHERE id = ?
                """,
                (blob, session_id),
            )


_deployment_session: DeploymentSession | None = None


def get_deployment_session() -> DeploymentSession:
    global _deployment_session
    if _deployment_session is None:
        _deployment_session = DeploymentSession()
    return _deployment_session


__all__ = ["DeploymentSession", "get_deployment_session"]

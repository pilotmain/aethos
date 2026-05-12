# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73 — :class:`MistakeMemory` for the Genesis Loop.

Stores fingerprints of failures the supervisor has already seen so the next
self-diagnosis pass can recognise repeats and prefer a recovery strategy that
worked last time. Embedding-based similarity is deferred (Phase 73b) — for v1
we use a deterministic substring fingerprint over the error string, which is
good enough to cluster e.g. "anthropic 429 rate_limit" repeats together.

The table lives inside the existing ``data/agent_audit.db`` SQLite database
(same connection-per-call pattern as :mod:`app.services.agent.activity_tracker`)
so we don't introduce a second SQLite file or a new alembic migration. Schema:

.. code-block:: sql

    CREATE TABLE mistakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        fingerprint TEXT NOT NULL,            -- normalized for similarity match
        error TEXT,
        cause_class TEXT,                     -- diagnosis bucket (e.g., 'repeated_llm_error')
        recovery_strategy TEXT,               -- last strategy attempted
        recovery_succeeded INTEGER NOT NULL DEFAULT 0,
        context TEXT,                         -- JSON blob
        occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
    )

All write paths swallow exceptions and log at WARN — recording a mistake must
never break the surrounding self-healing pass.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


_FP_NUM_RX = re.compile(r"\d+")
_FP_HEX_RX = re.compile(r"\b[0-9a-f]{6,}\b", re.IGNORECASE)
_FP_WS_RX = re.compile(r"\s+")
_FP_PUNCT_RX = re.compile(r"[\"'`<>(){}\[\]]")


def fingerprint_error(error: str | None) -> str:
    """
    Collapse an error string to a comparable fingerprint:
    lowercase, strip punctuation/quoting, replace numbers with ``N`` and long
    hex blobs with ``H``. Keeps the head 200 chars so two formatted exceptions
    with the same shape land on the same bucket regardless of stack ids.
    """
    if not error:
        return ""
    s = str(error)[:1000].lower()
    s = _FP_PUNCT_RX.sub(" ", s)
    s = _FP_HEX_RX.sub("H", s)
    s = _FP_NUM_RX.sub("N", s)
    s = _FP_WS_RX.sub(" ", s).strip()
    return s[:200]


class MistakeMemory:
    """SQLite-backed durable memory of past failures + recovery outcomes."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            settings = get_settings()
            root = Path(getattr(settings, "nexa_data_dir", "") or "data")
            db_path = root / "agent_audit.db"
        self.db_path = Path(db_path)
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
                    CREATE TABLE IF NOT EXISTS mistakes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_id TEXT NOT NULL,
                        fingerprint TEXT NOT NULL,
                        error TEXT,
                        cause_class TEXT,
                        recovery_strategy TEXT,
                        recovery_succeeded INTEGER NOT NULL DEFAULT 0,
                        context TEXT,
                        occurred_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mistakes_agent_id ON mistakes(agent_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_mistakes_fingerprint ON mistakes(fingerprint)"
                )

    def record_mistake(
        self,
        *,
        agent_id: str,
        error: str | None,
        cause_class: str | None = None,
        recovery_strategy: str | None = None,
        recovery_succeeded: bool = False,
        context: dict[str, Any] | None = None,
    ) -> int | None:
        """Insert a row. Returns the new id, or ``None`` on failure."""
        try:
            fp = fingerprint_error(error)
            ctx_blob = json.dumps(context or {}, default=str) if context else None
            with self._lock:
                with self._connect() as conn:
                    cur = conn.execute(
                        """
                        INSERT INTO mistakes
                            (agent_id, fingerprint, error, cause_class,
                             recovery_strategy, recovery_succeeded, context)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            (agent_id or "").strip()[:64],
                            fp,
                            (str(error) if error else None),
                            (cause_class or None),
                            (recovery_strategy or None),
                            1 if recovery_succeeded else 0,
                            ctx_blob,
                        ),
                    )
                    return int(cur.lastrowid) if cur.lastrowid is not None else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("MistakeMemory.record_mistake suppressed: %s", exc)
            return None

    def get_similar_mistakes(
        self,
        *,
        agent_id: str | None = None,
        error: str | None = None,
        fingerprint: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Return rows whose fingerprint matches (exact or substring overlap).
        Pass either ``error`` (will be fingerprinted) or a precomputed
        ``fingerprint``. Optionally scope to a single agent.
        """
        fp = (fingerprint if fingerprint is not None else fingerprint_error(error)).strip()
        if not fp:
            return []
        like = f"%{fp[:120]}%"  # keep the LIKE query bounded
        try:
            with self._lock:
                with self._connect() as conn:
                    if agent_id:
                        cur = conn.execute(
                            """
                            SELECT id, agent_id, fingerprint, error, cause_class,
                                   recovery_strategy, recovery_succeeded, context, occurred_at
                            FROM mistakes
                            WHERE agent_id = ?
                              AND (fingerprint = ? OR fingerprint LIKE ?)
                            ORDER BY datetime(occurred_at) DESC
                            LIMIT ?
                            """,
                            (agent_id, fp, like, max(1, int(limit))),
                        )
                    else:
                        cur = conn.execute(
                            """
                            SELECT id, agent_id, fingerprint, error, cause_class,
                                   recovery_strategy, recovery_succeeded, context, occurred_at
                            FROM mistakes
                            WHERE fingerprint = ? OR fingerprint LIKE ?
                            ORDER BY datetime(occurred_at) DESC
                            LIMIT ?
                            """,
                            (fp, like, max(1, int(limit))),
                        )
                    rows = cur.fetchall()
        except Exception as exc:  # noqa: BLE001
            logger.warning("MistakeMemory.get_similar_mistakes suppressed: %s", exc)
            return []
        out: list[dict[str, Any]] = []
        for r in rows:
            ctx_raw = r["context"]
            try:
                ctx = json.loads(ctx_raw) if ctx_raw else {}
            except Exception:
                ctx = {"raw": ctx_raw}
            out.append(
                {
                    "id": int(r["id"]),
                    "agent_id": r["agent_id"],
                    "fingerprint": r["fingerprint"],
                    "error": r["error"],
                    "cause_class": r["cause_class"],
                    "recovery_strategy": r["recovery_strategy"],
                    "recovery_succeeded": bool(r["recovery_succeeded"]),
                    "context": ctx,
                    "occurred_at": r["occurred_at"],
                }
            )
        return out

    def successful_strategy_for(self, fingerprint: str) -> str | None:
        """
        Look up the most recent recovery strategy that succeeded for this
        fingerprint. Used by the recovery handler to prefer a known-good fix.
        """
        if not fingerprint:
            return None
        try:
            with self._lock:
                with self._connect() as conn:
                    cur = conn.execute(
                        """
                        SELECT recovery_strategy
                        FROM mistakes
                        WHERE fingerprint = ?
                          AND recovery_succeeded = 1
                          AND recovery_strategy IS NOT NULL
                        ORDER BY datetime(occurred_at) DESC
                        LIMIT 1
                        """,
                        (fingerprint,),
                    )
                    row = cur.fetchone()
        except Exception as exc:  # noqa: BLE001
            logger.warning("MistakeMemory.successful_strategy_for suppressed: %s", exc)
            return None
        return row["recovery_strategy"] if row else None


_mistake_memory: MistakeMemory | None = None


def get_mistake_memory() -> MistakeMemory:
    global _mistake_memory
    if _mistake_memory is None:
        _mistake_memory = MistakeMemory()
    return _mistake_memory


__all__ = [
    "MistakeMemory",
    "fingerprint_error",
    "get_mistake_memory",
]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""SQLite-backed daily usage rollups for billing-style metering (tokens / requests)."""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.core.config import REPO_ROOT as _REPO_ROOT


class UsageTracker:
    """Persist per-user daily aggregates under ``data/billing_usage.sqlite``."""

    def __init__(self, db_path: Path | None = None) -> None:
        root = Path(_REPO_ROOT).resolve()
        data_dir = root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = db_path or (data_dir / "billing_usage.sqlite")
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._path), timeout=30)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_daily (
                    user_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    tokens INTEGER NOT NULL DEFAULT 0,
                    requests INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, day)
                )
                """
            )

    def record_usage(self, user_id: str, tokens: int = 0, requests: int = 1) -> None:
        uid = (user_id or "").strip()[:128]
        if not uid:
            return
        today = date.today().isoformat()
        tok = max(0, int(tokens))
        req = max(0, int(requests))
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO usage_daily (user_id, day, tokens, requests)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, day) DO UPDATE SET
                  tokens = tokens + excluded.tokens,
                  requests = requests + excluded.requests
                """,
                (uid, today, tok, req),
            )

    def get_monthly_usage(self, user_id: str) -> dict[str, int]:
        """Sum tokens and requests from the first day of this month through today (UTC date)."""
        uid = (user_id or "").strip()[:128]
        if not uid:
            return {"tokens": 0, "requests": 0}
        now = datetime.now(timezone.utc).date()
        start = date(now.year, now.month, 1).isoformat()
        end = now.isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COALESCE(SUM(tokens), 0), COALESCE(SUM(requests), 0)
                FROM usage_daily
                WHERE user_id = ? AND day >= ? AND day <= ?
                """,
                (uid, start, end),
            ).fetchone()
        if not row:
            return {"tokens": 0, "requests": 0}
        return {"tokens": int(row[0]), "requests": int(row[1])}

    def get_last_days(self, user_id: str, days: int = 30) -> list[dict[str, int | str]]:
        uid = (user_id or "").strip()[:128]
        if not uid:
            return []
        end = date.today()
        start = end - timedelta(days=max(1, int(days)) - 1)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT day, tokens, requests FROM usage_daily
                WHERE user_id = ? AND day >= ? AND day <= ?
                ORDER BY day ASC
                """,
                (uid, start.isoformat(), end.isoformat()),
            ).fetchall()
        return [{"day": r[0], "tokens": int(r[1]), "requests": int(r[2])} for r in rows]


def track_usage(user_id: str, metric: str, quantity: int = 1) -> None:
    """Record usage for metered billing (SQLite rollup)."""
    uid = (user_id or "").strip()
    if not uid:
        return
    m = (metric or "api_call").strip().lower()
    q = max(1, int(quantity))
    tracker = UsageTracker()
    if m == "tokens":
        tracker.record_usage(uid, tokens=q, requests=0)
    else:
        tracker.record_usage(uid, tokens=0, requests=q)


__all__ = ["UsageTracker", "track_usage"]

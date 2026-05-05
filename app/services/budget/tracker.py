"""
Budget and usage tracking service (Phase 28).
"""

from __future__ import annotations

import calendar
import json
import logging
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.budget.models import BudgetStatus, MemberBudget, UsageRecord, UsageType

logger = logging.getLogger(__name__)


def _parse_date_stored(raw: str | None) -> date | None:
    if not raw:
        return None
    s = raw.strip()
    try:
        if "T" in s:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _period_start(today: date, reset_day: int) -> date:
    """Start of the current budget period (anchored on reset_day, 1–28)."""
    rd = max(1, min(28, reset_day))
    dim = calendar.monthrange(today.year, today.month)[1]
    anchor = min(rd, dim)
    if today.day >= anchor:
        return date(today.year, today.month, anchor)
    first = today.replace(day=1)
    prev_end = first - timedelta(days=1)
    py, pm = prev_end.year, prev_end.month
    dim_prev = calendar.monthrange(py, pm)[1]
    return date(py, pm, min(rd, dim_prev))


class BudgetTracker:
    """Track and enforce budget limits for team members."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is not None:
            self.db_path = Path(db_path)
        else:
            settings = get_settings()
            base = Path(getattr(settings, "nexa_data_dir", None) or "data")
            self.db_path = base / "budget.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS member_budgets (
                    member_id TEXT PRIMARY KEY,
                    monthly_limit INTEGER NOT NULL,
                    current_usage INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    warning_sent_80 INTEGER DEFAULT 0,
                    warning_sent_95 INTEGER DEFAULT 0,
                    reset_day INTEGER DEFAULT 1,
                    last_reset TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_records (
                    id TEXT PRIMARY KEY,
                    member_id TEXT NOT NULL,
                    member_name TEXT,
                    usage_type TEXT NOT NULL,
                    tokens INTEGER NOT NULL,
                    estimated_cost_usd REAL DEFAULT 0,
                    description TEXT,
                    project_id TEXT,
                    task_id TEXT,
                    metadata TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_member ON usage_records(member_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_created ON usage_records(created_at)")
        self._apply_org_columns()

    def _apply_org_columns(self) -> None:
        """Phase 29 — optional tenant columns on member_budgets."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(member_budgets)")
            existing_columns = {str(row[1]) for row in cursor.fetchall()}

            def _add_column_if_missing(col: str, ddl: str) -> None:
                if col in existing_columns:
                    return
                try:
                    conn.execute(ddl)
                    existing_columns.add(col)
                except sqlite3.OperationalError as exc:
                    # Race: another connection added the column; ignore duplicate.
                    if "duplicate column" not in str(exc).lower():
                        raise

            _add_column_if_missing(
                "organization_id",
                "ALTER TABLE member_budgets ADD COLUMN organization_id TEXT",
            )
            _add_column_if_missing(
                "team_id",
                "ALTER TABLE member_budgets ADD COLUMN team_id TEXT",
            )

    def get_or_create_budget(
        self, member_id: str, monthly_limit: int | None = None
    ) -> MemberBudget:
        settings = get_settings()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT * FROM member_budgets WHERE member_id = ?",
                (member_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_budget(row)

            rd = int(getattr(settings, "nexa_budget_reset_day", 1) or 1)
            rd = max(1, min(28, rd))
            today = date.today()
            ps = _period_start(today, rd)
            budget = MemberBudget(
                member_id=member_id,
                monthly_limit=monthly_limit
                or int(getattr(settings, "nexa_budget_default_monthly_limit", 1_000_000)),
                current_usage=0,
                last_reset=ps,
                reset_day=rd,
            )
            self._save_budget(budget)
            return budget

    def _save_budget(self, budget: MemberBudget) -> None:
        budget.updated_at = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO member_budgets
                (member_id, monthly_limit, current_usage, status,
                 warning_sent_80, warning_sent_95, reset_day, last_reset,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    budget.member_id,
                    budget.monthly_limit,
                    budget.current_usage,
                    budget.status.value,
                    1 if budget.warning_sent_80 else 0,
                    1 if budget.warning_sent_95 else 0,
                    budget.reset_day,
                    budget.last_reset.isoformat() if budget.last_reset else None,
                    budget.created_at.isoformat(),
                    budget.updated_at.isoformat(),
                ),
            )

    def _row_to_budget(self, row: tuple[Any, ...]) -> MemberBudget:
        lr = _parse_date_stored(row[7])
        c_at = datetime.fromisoformat(str(row[8]).replace("Z", "+00:00"))
        u_at = datetime.fromisoformat(str(row[9]).replace("Z", "+00:00"))
        return MemberBudget(
            member_id=str(row[0]),
            monthly_limit=int(row[1]),
            current_usage=int(row[2]),
            status=BudgetStatus(row[3]),
            warning_sent_80=bool(row[4]),
            warning_sent_95=bool(row[5]),
            reset_day=int(row[6]),
            last_reset=lr,
            created_at=c_at,
            updated_at=u_at,
        )

    def check_and_reset_budget(self, member_id: str) -> bool:
        """Roll into a new period when ``last_reset`` is before the current period start."""
        budget = self.get_or_create_budget(member_id)
        settings = get_settings()
        rd = budget.reset_day or int(getattr(settings, "nexa_budget_reset_day", 1) or 1)
        rd = max(1, min(28, rd))
        today = date.today()
        period_start = _period_start(today, rd)
        lr = budget.last_reset
        if lr is None or lr < period_start:
            budget.current_usage = 0
            budget.status = BudgetStatus.ACTIVE
            budget.warning_sent_80 = False
            budget.warning_sent_95 = False
            budget.last_reset = period_start
            budget.updated_at = datetime.now()
            self._save_budget(budget)
            logger.info("Reset budget period for member %s at %s", member_id, period_start)
            return True
        return False

    def _sync_status_from_usage(self, budget: MemberBudget) -> None:
        if budget.status == BudgetStatus.OVERRIDE:
            return
        pct = budget.usage_percentage()
        if pct >= 100 or budget.is_exhausted():
            budget.status = BudgetStatus.PAUSED
        elif pct >= 80:
            budget.status = BudgetStatus.WARNING
        else:
            budget.status = BudgetStatus.ACTIVE

    def _fire_warnings(self, budget: MemberBudget) -> None:
        mid = budget.member_id
        if budget.should_warn_80():
            budget.warning_sent_80 = True
            logger.warning(
                "Budget 80%% warning member=%s usage=%s limit=%s",
                mid,
                budget.current_usage,
                budget.monthly_limit,
            )
        if budget.should_warn_95():
            budget.warning_sent_95 = True
            logger.warning(
                "Budget 95%% warning member=%s usage=%s limit=%s",
                mid,
                budget.current_usage,
                budget.monthly_limit,
            )

    def record_usage(
        self,
        member_id: str,
        tokens: int,
        usage_type: UsageType = UsageType.LLM_CALL,
        description: str | None = None,
        member_name: str | None = None,
        project_id: str | None = None,
        task_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageRecord | None:
        self.check_and_reset_budget(member_id)
        budget = self.get_or_create_budget(member_id)
        if budget.status == BudgetStatus.OVERRIDE:
            pass
        elif not budget.can_execute(tokens):
            logger.warning(
                "Member %s budget exhausted, cannot record %s tokens", member_id, tokens
            )
            return None

        record = UsageRecord.create(
            member_id=member_id,
            tokens=tokens,
            usage_type=usage_type,
            description=description,
        )
        record.member_name = member_name
        record.project_id = project_id
        record.task_id = task_id
        if metadata:
            record.metadata.update(metadata)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO usage_records
                (id, member_id, member_name, usage_type, tokens, estimated_cost_usd,
                 description, project_id, task_id, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.member_id,
                    record.member_name,
                    record.usage_type.value,
                    record.tokens,
                    record.estimated_cost_usd,
                    record.description,
                    record.project_id,
                    record.task_id,
                    json.dumps(record.metadata),
                    record.created_at.isoformat(),
                ),
            )

        if budget.status != BudgetStatus.OVERRIDE:
            budget.current_usage += tokens
        self._fire_warnings(budget)
        self._sync_status_from_usage(budget)
        self._save_budget(budget)
        logger.info("Recorded %s tokens for member %s (%s)", tokens, member_id, usage_type.value)
        return record

    def get_usage(self, member_id: str, days: int = 30) -> list[UsageRecord]:
        cutoff = datetime.now() - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT * FROM usage_records
                WHERE member_id = ? AND created_at >= ?
                ORDER BY created_at DESC
                """,
                (member_id, cutoff.isoformat()),
            )
            return [self._row_to_record(r) for r in cursor.fetchall()]

    def get_team_usage(self, member_ids: list[str], days: int = 30) -> list[UsageRecord]:
        if not member_ids:
            return []
        placeholders = ",".join(["?"] * len(member_ids))
        cutoff = datetime.now() - timedelta(days=days)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"""
                SELECT * FROM usage_records
                WHERE member_id IN ({placeholders}) AND created_at >= ?
                ORDER BY created_at DESC
                """,
                (*member_ids, cutoff.isoformat()),
            )
            return [self._row_to_record(r) for r in cursor.fetchall()]

    def get_team_summary(self, member_ids: list[str]) -> dict[str, Any]:
        summary: dict[str, dict[str, Any]] = {}
        for mid in member_ids:
            self.check_and_reset_budget(mid)
            budget = self.get_or_create_budget(mid)
            summary[mid] = {
                "used": budget.current_usage,
                "limit": budget.monthly_limit,
                "remaining": budget.remaining(),
                "percentage": budget.usage_percentage(),
                "status": budget.status.value,
                "can_execute": budget.can_execute(),
            }
        total_used = sum(s["used"] for s in summary.values())
        total_limit = sum(s["limit"] for s in summary.values())
        return {
            "members": summary,
            "team_total_used": total_used,
            "team_total_limit": total_limit,
            "team_remaining": max(0, total_limit - total_used),
            "team_percentage": (total_used / total_limit * 100) if total_limit > 0 else 0.0,
        }

    def _row_to_record(self, row: tuple[Any, ...]) -> UsageRecord:
        return UsageRecord(
            id=str(row[0]),
            member_id=str(row[1]),
            member_name=row[2],
            usage_type=UsageType(row[3]),
            tokens=int(row[4]),
            estimated_cost_usd=float(row[5] or 0),
            description=row[6],
            project_id=row[7],
            task_id=row[8],
            metadata=json.loads(row[9]) if row[9] else {},
            created_at=datetime.fromisoformat(str(row[10]).replace("Z", "+00:00")),
        )

    def adjust_budget(self, member_id: str, token_delta: int, reason: str) -> bool:
        """
        Manual adjustment: positive ``token_delta`` grants headroom (reduces recorded usage);
        negative ``token_delta`` increases usage (e.g. correction).
        """
        self.check_and_reset_budget(member_id)
        budget = self.get_or_create_budget(member_id)
        if token_delta >= 0:
            budget.current_usage = max(0, budget.current_usage - token_delta)
        else:
            budget.current_usage = max(0, budget.current_usage + (-token_delta))
        self._sync_status_from_usage(budget)
        self._save_budget(budget)
        logger.info(
            "Adjusted budget for %s by %+d (reason=%s)", member_id, token_delta, reason[:200]
        )
        return True

    def set_budget_limit(self, member_id: str, new_limit: int) -> bool:
        self.check_and_reset_budget(member_id)
        budget = self.get_or_create_budget(member_id)
        budget.monthly_limit = max(0, new_limit)
        self._sync_status_from_usage(budget)
        self._save_budget(budget)
        logger.info("Set budget limit for %s to %s", member_id, new_limit)
        return True

    def pause_member(self, member_id: str) -> bool:
        budget = self.get_or_create_budget(member_id)
        budget.status = BudgetStatus.PAUSED
        self._save_budget(budget)
        logger.info("Paused member %s", member_id)
        return True

    def resume_member(self, member_id: str) -> bool:
        budget = self.get_or_create_budget(member_id)
        if budget.status == BudgetStatus.OVERRIDE:
            self._save_budget(budget)
            return True
        if budget.current_usage >= budget.monthly_limit and budget.monthly_limit > 0:
            logger.warning("Cannot resume %s: budget exhausted", member_id)
            return False
        budget.status = BudgetStatus.ACTIVE
        self._sync_status_from_usage(budget)
        self._save_budget(budget)
        logger.info("Resumed member %s", member_id)
        return True

    def set_override(self, member_id: str, enabled: bool) -> bool:
        budget = self.get_or_create_budget(member_id)
        budget.status = BudgetStatus.OVERRIDE if enabled else BudgetStatus.ACTIVE
        self._sync_status_from_usage(budget)
        self._save_budget(budget)
        return True


__all__ = ["BudgetTracker"]

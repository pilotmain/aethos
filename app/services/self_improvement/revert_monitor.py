"""
Phase 73e — periodic in-process auto-revert monitor.

Watches the most-recent self-improvement proposal that flipped to
``merged`` (Phase 73c GitHub flow) and, if the agent-audit ``mistakes``
table shows a regression during the observation window, opens a revert
PR via the existing :func:`GitHubClient.open_revert_pr` (Phase 73c).

Design notes (safe-adapt):

* **Open the revert PR; do NOT auto-merge it.** The 73d ``auto_merge_on_ci``
  flow is the right place to land an operator-supervised merge. v1
  deliberately leaves the revert PR open so a recovering health flap
  can't trigger an immediate revert/un-revert loop.
* **Observation window.** A merged proposal is only considered for at
  most ``NEXA_SELF_IMPROVEMENT_REVERT_MIN_OBSERVATION_WINDOW_SECONDS``
  (default 5 min) after its ``merged_at``. After that the monitor marks
  it ``auto_revert_state="cleared"`` and stops looking.
* **Min sample size + post-restart grace.** A regression is declared
  only when (a) at least ``_REVERT_MIN_SAMPLE_SIZE`` mistakes have been
  recorded inside the window, AND (b) the rolling error rate over the
  same window exceeds ``_REVERT_ERROR_RATE_THRESHOLD``, AND (c) at
  least ``_REVERT_POST_RESTART_GRACE_SECONDS`` have elapsed since this
  process started. This protects against the in-flight-request error
  blip that always follows a uvicorn-reload restart.
* **/health non-200 + heartbeat staleness escalate; they do not revert.**
  Loss of liveness is an availability problem (calling out to the GitHub
  REST API to open a revert PR won't help) — that signal is surfaced via
  ``/health/detailed`` and via the existing 73 supervisor escalation
  path, not here.
* **Cooldown.** After a revert fires, ``app.services.agent.system_state``
  records ``last_auto_revert_at``. The 73d ``ci_monitor`` consults that
  timestamp and pauses auto-merge-on-CI for
  ``_REVERT_COOLDOWN_MINUTES`` minutes; manual operator merges (via the
  ``/merge-pr`` endpoint) still work. The cooldown is intentionally a
  soft pause on the auto-pipeline only.
* **DB-driven recovery.** Like the 73d CI monitor, all state lives in
  the proposal store and the system_state table. Restarting the API
  mid-observation-window doesn't lose the watch.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.agent.system_state import get_system_state
from app.services.self_improvement.github_client import (
    GitHubClient,
    GitHubError,
    get_github_client,
)
from app.services.self_improvement.proposal import (
    STATUS_MERGED,
    STATUS_REVERT_PR_OPEN,
    Proposal,
    ProposalStore,
    get_proposal_store,
)

logger = logging.getLogger(__name__)


# --- Regression metrics --------------------------------------------------


def fetch_error_rate_window(*, window_seconds: int) -> dict[str, Any]:
    """Compute ``{total, errors, error_rate}`` over the trailing window.

    Reads from ``agent_audit.db`` ``agent_actions`` directly; we don't go
    through :class:`AgentActivityTracker` so we can scope the query to a
    wall-clock window without holding the tracker's lock for non-trivial
    aggregation work. Returns zeros (and ``error_rate=0.0``) on any
    failure — the monitor must never trigger off a partial read.
    """
    settings = get_settings()
    root = Path(getattr(settings, "nexa_data_dir", "") or "data")
    db_path = root / "agent_audit.db"
    out = {"total": 0, "errors": 0, "error_rate": 0.0, "window_seconds": int(window_seconds)}
    if not db_path.exists():
        return out
    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COALESCE(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END), 0) AS errors
                FROM agent_actions
                WHERE datetime(created_at) >=
                    datetime('now', ?)
                """,
                (f"-{int(window_seconds)} seconds",),
            )
            row = cur.fetchone()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("revert_monitor: error_rate query suppressed: %s", exc)
        return out
    if not row:
        return out
    total = int(row["total"] or 0)
    errors = int(row["errors"] or 0)
    rate = (errors / total) if total > 0 else 0.0
    out.update({"total": total, "errors": errors, "error_rate": float(rate)})
    return out


# --- Monitor task --------------------------------------------------------


class RevertMonitor:
    """Single periodic asyncio task, owned by the API process."""

    def __init__(
        self,
        *,
        store: ProposalStore | None = None,
        client: GitHubClient | None = None,
    ) -> None:
        self._store = store
        self._client = client
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._kick = asyncio.Event()

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        s = get_settings()
        if not bool(getattr(s, "nexa_self_improvement_enabled", False)):
            logger.info("revert_monitor: self_improvement disabled, not starting")
            return
        if not bool(getattr(s, "nexa_self_improvement_github_enabled", False)):
            logger.info("revert_monitor: github flow disabled, not starting")
            return
        if not bool(getattr(s, "nexa_self_improvement_auto_revert_enabled", False)):
            logger.info("revert_monitor: auto_revert disabled, not starting")
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("revert_monitor.start called outside an event loop; skipping")
            return
        self._stop.clear()
        self._kick.clear()
        self._task = loop.create_task(self._run(), name="self_improvement_revert_monitor")
        logger.info(
            "revert_monitor: started (interval=%ss, window=%ss, threshold=%.2f, min_sample=%s)",
            int(getattr(s, "nexa_self_improvement_revert_health_check_interval_seconds", 30) or 30),
            int(getattr(s, "nexa_self_improvement_revert_min_observation_window_seconds", 300) or 300),
            float(getattr(s, "nexa_self_improvement_revert_error_rate_threshold", 0.3) or 0.3),
            int(getattr(s, "nexa_self_improvement_revert_min_sample_size", 10) or 10),
        )

    async def stop(self) -> None:
        self._stop.set()
        self._kick.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
        self._task = None
        logger.info("revert_monitor: stopped")

    def kick_now(self) -> None:
        """Wake the monitor outside the regular interval (best-effort).

        Called by the supervisor on a healthy→unhealthy transition so we
        don't have to wait up to ``_REVERT_HEALTH_CHECK_INTERVAL_SECONDS``
        for the next scheduled scan. Safe to call from any thread or
        event loop — only sets a flag.
        """
        try:
            self._kick.set()
        except Exception:  # noqa: BLE001
            pass

    # --- main loop -------------------------------------------------------

    async def _run(self) -> None:
        s = get_settings()
        interval = max(
            5,
            int(getattr(s, "nexa_self_improvement_revert_health_check_interval_seconds", 30) or 30),
        )
        while not self._stop.is_set():
            try:
                await self.scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("revert_monitor: scan_once raised; continuing")
            # Sleep until either the timer fires, or kick_now() / stop() arrives.
            try:
                await asyncio.wait_for(self._kick.wait(), timeout=interval)
                self._kick.clear()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # --- one scan pass ---------------------------------------------------

    async def scan_once(self) -> dict[str, int]:
        """Evaluate every merged proposal in the observation window once.

        Returns a small counters dict so the test suite can introspect
        what happened without scraping logs.
        """
        store = self._store or get_proposal_store()
        s = get_settings()
        window_s = max(
            60,
            int(
                getattr(s, "nexa_self_improvement_revert_min_observation_window_seconds", 300) or 300
            ),
        )

        counters = {
            "scanned": 0, "watched": 0, "cleared": 0,
            "skipped_disabled": 0, "skipped_grace": 0,
            "skipped_low_sample": 0, "skipped_below_threshold": 0,
            "reverted": 0, "revert_errors": 0,
        }

        proposals = store.list_recent_merged_within(window_seconds=window_s)
        counters["scanned"] = len(proposals)
        if not proposals:
            return counters

        # Compute the metric ONCE per scan — every proposal in the window
        # shares the same trailing error-rate so we don't have to make N
        # queries.
        metrics = fetch_error_rate_window(window_seconds=window_s)
        threshold = float(
            getattr(s, "nexa_self_improvement_revert_error_rate_threshold", 0.3) or 0.3
        )
        min_sample = max(
            1,
            int(getattr(s, "nexa_self_improvement_revert_min_sample_size", 10) or 10),
        )
        grace_s = max(
            0,
            int(getattr(s, "nexa_self_improvement_revert_post_restart_grace_seconds", 60) or 60),
        )

        sysstate = get_system_state()
        process_age = sysstate.process_age_seconds()
        post_restart_ok = process_age is None or process_age >= grace_s

        for p in proposals:
            await self._evaluate(
                p,
                store=store,
                metrics=metrics,
                threshold=threshold,
                min_sample=min_sample,
                post_restart_ok=post_restart_ok,
                window_s=window_s,
                counters=counters,
            )
        return counters

    async def _evaluate(
        self,
        p: Proposal,
        *,
        store: ProposalStore,
        metrics: dict[str, Any],
        threshold: float,
        min_sample: int,
        post_restart_ok: bool,
        window_s: int,
        counters: dict[str, int],
    ) -> None:
        # Already in revert flow → mark cleared so we stop looking.
        if p.status == STATUS_REVERT_PR_OPEN:
            store.set_auto_revert_state(p.id, state="cleared")
            counters["cleared"] += 1
            return

        if p.auto_revert_disabled:
            store.set_auto_revert_state(p.id, state="disabled")
            counters["skipped_disabled"] += 1
            return

        # Past the observation window → cleared. (list_recent_merged_within
        # already filters, but defensive against clock skew.)
        merged_age = store.get_merged_age_seconds(p.id) or 0.0
        if merged_age > window_s:
            store.set_auto_revert_state(p.id, state="cleared")
            counters["cleared"] += 1
            return

        if not post_restart_ok:
            counters["skipped_grace"] += 1
            return

        total = int(metrics.get("total") or 0)
        errors = int(metrics.get("errors") or 0)
        rate = float(metrics.get("error_rate") or 0.0)

        if errors < min_sample:
            counters["skipped_low_sample"] += 1
            store.set_auto_revert_state(p.id, state="watching")
            counters["watched"] += 1
            return
        if rate < threshold:
            counters["skipped_below_threshold"] += 1
            store.set_auto_revert_state(p.id, state="watching")
            counters["watched"] += 1
            return

        # All gates passed → fire revert.
        client = self._client or get_github_client()
        if not client.enabled or not client.has_token:
            logger.warning(
                "revert_monitor: would revert proposal=%s but github client is not configured "
                "(enabled=%s has_token=%s); marking cleared",
                p.id, client.enabled, client.has_token,
            )
            store.set_auto_revert_state(p.id, state="cleared")
            counters["cleared"] += 1
            return
        if not p.merge_commit_sha:
            logger.warning(
                "revert_monitor: would revert proposal=%s but merge_commit_sha is empty; cleared",
                p.id,
            )
            store.set_auto_revert_state(p.id, state="cleared")
            counters["cleared"] += 1
            return

        try:
            revert_pr = await client.open_revert_pr(
                merge_commit_sha=p.merge_commit_sha,
                title=f"Revert {p.title} (auto)",
                body=_build_revert_body(p, total=total, errors=errors, rate=rate, window_s=window_s),
            )
        except GitHubError as exc:
            counters["revert_errors"] += 1
            logger.warning(
                "revert_monitor: open_revert_pr failed proposal=%s err=%s",
                p.id, exc,
            )
            return

        store.set_github_state(
            p.id,
            new_status=STATUS_REVERT_PR_OPEN,
            revert_pr_number=revert_pr.number,
            revert_pr_url=revert_pr.url,
        )
        store.set_auto_revert_state(p.id, state="reverted")
        get_system_state().mark_auto_revert(proposal_id=p.id)
        counters["reverted"] += 1
        logger.warning(
            "revert_monitor: opened revert PR #%s for proposal=%s "
            "(error_rate=%.2f over %ss with %s mistakes)",
            revert_pr.number, p.id, rate, window_s, errors,
        )


# --- helpers -------------------------------------------------------------


def _build_revert_body(
    p: Proposal,
    *,
    total: int,
    errors: int,
    rate: float,
    window_s: int,
) -> str:
    pct = rate * 100.0
    pr_ref = f"#{p.pr_number}" if p.pr_number else "(no PR number)"
    return (
        f"### Auto-revert from AethOS Phase 73e\n\n"
        f"This PR reverts the merge commit `{(p.merge_commit_sha or '')[:12]}` "
        f"introduced by self-improvement proposal `{p.id}` ({pr_ref}).\n\n"
        f"**Trigger:** during the {window_s}s observation window after merge, "
        f"the agent-audit `mistakes` table recorded **{errors}/{total}** failed "
        f"actions (≈ **{pct:.1f}%** error rate), exceeding the configured threshold.\n\n"
        f"This revert PR was opened automatically and is **not** auto-merged. "
        f"Operator review is required before landing.\n\n"
        f"### Original problem statement\n\n{p.problem_statement.strip()}\n"
    )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --- singleton -----------------------------------------------------------


_monitor: RevertMonitor | None = None


def get_revert_monitor() -> RevertMonitor:
    global _monitor
    if _monitor is None:
        _monitor = RevertMonitor()
    return _monitor


__all__ = [
    "RevertMonitor",
    "fetch_error_rate_window",
    "get_revert_monitor",
]

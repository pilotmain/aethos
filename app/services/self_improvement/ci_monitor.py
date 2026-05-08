"""
Phase 73d — periodic in-process CI status monitor for self-improvement PRs.

Design notes:

* **DB-driven recovery.** State lives in :mod:`app.services.self_improvement.proposal`'s
  SQLite store, not in-memory. If the API restarts mid-poll, the next scan
  picks up where we left off.
* **Single periodic task** instead of one task per PR. Wakes every
  :data:`Settings.nexa_self_improvement_ci_poll_interval_seconds`, queries
  every proposal in ``pr_open``, updates ``ci_state`` / ``ci_details``.
  Bounded by GitHub's rate limit naturally — we cap concurrent calls at 4.
* **Hard max-age.** A PR whose CI has been pending for longer than
  :data:`Settings.nexa_self_improvement_ci_max_age_seconds` is marked
  ``ci_state="timed_out"`` and stops being polled. Operator can re-trigger
  via the manual ``/refresh-ci`` endpoint.
* **Auto-merge handoff.** When CI flips to ``"success"`` and the proposal
  has ``auto_merge_on_ci_pass=True``, we check the local sandbox freshness
  (Phase 73b's 60-second gate). Fresh → call the GitHub merge directly.
  Stale → set ``ci_state="passed_awaiting_sandbox"`` so the UI surfaces a
  "re-run sandbox + merge" prompt and we never block here.
* **Auto-restart handoff.** When a merge lands and
  :func:`app.core.restart.restart_enabled` is true, we schedule the
  restart via the same machinery the API endpoint uses. The scanner's
  own task disappears with the process — that's intentional.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.self_improvement.github_client import (
    GitHubClient,
    GitHubError,
    get_github_client,
)
from app.services.self_improvement.proposal import (
    APPLY_REQUIRES_FRESH_SANDBOX_S,
    STATUS_MERGED,
    STATUS_PR_OPEN,
    Proposal,
    ProposalStore,
    get_proposal_store,
)

logger = logging.getLogger(__name__)


_MAX_CONCURRENT_POLLS = 4


class CiMonitor:
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

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        s = get_settings()
        if not bool(getattr(s, "nexa_self_improvement_enabled", False)):
            logger.info("ci_monitor: self_improvement disabled, not starting")
            return
        if not bool(getattr(s, "nexa_self_improvement_github_enabled", False)):
            logger.info("ci_monitor: github flow disabled, not starting")
            return
        if not bool(getattr(s, "nexa_self_improvement_wait_for_ci", True)):
            logger.info("ci_monitor: wait_for_ci=false, not starting")
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("ci_monitor.start called outside an event loop; skipping")
            return
        self._stop.clear()
        self._task = loop.create_task(self._run(), name="self_improvement_ci_monitor")
        logger.info("ci_monitor: started (interval=%ss)",
                    int(getattr(s, "nexa_self_improvement_ci_poll_interval_seconds", 30) or 30))

    async def stop(self) -> None:
        self._stop.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
        self._task = None
        logger.info("ci_monitor: stopped")

    # --- main loop -------------------------------------------------------

    async def _run(self) -> None:
        s = get_settings()
        interval = max(5, int(getattr(s, "nexa_self_improvement_ci_poll_interval_seconds", 30) or 30))
        while not self._stop.is_set():
            try:
                await self.scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("ci_monitor: scan_once raised; continuing")
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # --- one scan pass ---------------------------------------------------

    async def scan_once(self) -> dict[str, int]:
        """Poll every ``pr_open`` proposal once. Returns counters for tests."""
        store = self._store or get_proposal_store()
        client = self._client or get_github_client()
        s = get_settings()
        max_age_s = max(60, int(getattr(s, "nexa_self_improvement_ci_max_age_seconds", 21600) or 21600))

        proposals = store.list_pr_open()
        counters = {
            "scanned": 0, "pending": 0, "passed": 0, "failed": 0,
            "errored": 0, "timed_out": 0, "merged": 0, "awaiting_sandbox": 0,
        }
        if not proposals:
            return counters

        sem = asyncio.Semaphore(_MAX_CONCURRENT_POLLS)

        async def _poll_one(p: Proposal) -> None:
            async with sem:
                await self._poll_proposal(p, store=store, client=client, max_age_s=max_age_s, counters=counters)

        await asyncio.gather(*(_poll_one(p) for p in proposals), return_exceptions=True)
        counters["scanned"] = len(proposals)
        return counters

    async def _poll_proposal(
        self,
        p: Proposal,
        *,
        store: ProposalStore,
        client: GitHubClient,
        max_age_s: int,
        counters: dict[str, int],
    ) -> None:
        if not p.pr_number:
            return
        try:
            ci = await client.get_pr_ci_status(p.pr_number)
        except GitHubError as exc:
            logger.warning(
                "ci_monitor: get_pr_ci_status failed proposal=%s pr=%s err=%s",
                p.id, p.pr_number, exc,
            )
            return

        ci_details = {
            "head_sha": ci.head_sha,
            "total_count": ci.total_count,
            "checks": [
                {"name": c.name, "source": c.source, "state": c.state, "url": c.url}
                for c in ci.checks
            ],
        }

        if ci.state == "pending":
            now = _utc_now_iso()
            store.set_ci_state(
                p.id,
                ci_state="pending",
                ci_details=ci_details,
                ci_first_seen_pending_at=now,
            )
            counters["pending"] += 1
            # Max-age timeout?
            refreshed = store.get(p.id)
            if (
                refreshed
                and refreshed.ci_first_seen_pending_at
                and _seconds_since_iso(refreshed.ci_first_seen_pending_at) > max_age_s
            ):
                store.set_ci_state(p.id, ci_state="timed_out", ci_details=ci_details)
                counters["timed_out"] += 1
            return

        if ci.state == "failure":
            store.set_ci_state(p.id, ci_state="failure", ci_details=ci_details)
            counters["failed"] += 1
            return
        if ci.state == "error":
            store.set_ci_state(p.id, ci_state="error", ci_details=ci_details)
            counters["errored"] += 1
            return
        if ci.state == "success":
            store.set_ci_state(p.id, ci_state="success", ci_details=ci_details)
            counters["passed"] += 1
            # Auto-merge handoff.
            if not p.auto_merge_on_ci_pass:
                return
            sandbox_age = store.get_sandbox_run_age_seconds(p.id)
            if sandbox_age is None or sandbox_age > APPLY_REQUIRES_FRESH_SANDBOX_S:
                store.set_ci_state(
                    p.id, ci_state="passed_awaiting_sandbox", ci_details=ci_details
                )
                counters["awaiting_sandbox"] += 1
                logger.info(
                    "ci_monitor: ci passed but local sandbox stale "
                    "proposal=%s sandbox_age=%s s",
                    p.id, sandbox_age,
                )
                return
            # Sandbox is fresh — perform the merge.
            try:
                merge = await client.merge_pull_request(
                    p.pr_number,
                    commit_title=f"{client.pr_title_prefix} {p.title}",
                    commit_message=(p.rationale or "").strip() or None,
                )
            except GitHubError as exc:
                logger.warning(
                    "ci_monitor: auto-merge failed proposal=%s pr=%s err=%s",
                    p.id, p.pr_number, exc,
                )
                return
            store.set_github_state(
                p.id,
                new_status=STATUS_MERGED,
                merge_commit_sha=merge.merge_commit_sha,
            )
            counters["merged"] += 1
            logger.info(
                "ci_monitor: auto-merged proposal=%s pr=%s sha=%s",
                p.id, p.pr_number, merge.merge_commit_sha,
            )
            # Auto-restart handoff (best-effort; tracker logs in restart module).
            try:
                from app.core.restart import restart_enabled, schedule_restart
                if restart_enabled():
                    await schedule_restart(delay_s=2.0)
            except Exception:  # noqa: BLE001
                logger.exception("ci_monitor: schedule_restart raised; continuing")


# --- helpers + module singleton ------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _seconds_since_iso(ts: str) -> float:
    """Parse a ``ci_first_seen_pending_at`` SQLite-style timestamp.

    SQLite ``datetime('now')`` returns ``YYYY-MM-DD HH:MM:SS`` in UTC; we
    treat any other input as ``+inf`` (never times out) for safety.
    """
    try:
        if "T" in ts:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return 0.0
    return (datetime.now(timezone.utc) - dt).total_seconds()


_monitor: CiMonitor | None = None


def get_ci_monitor() -> CiMonitor:
    global _monitor
    if _monitor is None:
        _monitor = CiMonitor()
    return _monitor


__all__ = ["CiMonitor", "get_ci_monitor"]


# Suppress "unused" warnings on Any until a typed callback signature lands.
_ = Any

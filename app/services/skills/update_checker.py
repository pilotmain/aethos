"""
Phase 75 — periodic ClawHub skill update checker.

This module mirrors the lifecycle pattern established by
:mod:`app.services.self_improvement.ci_monitor` /
:mod:`app.services.self_improvement.revert_monitor`:

* a single in-process asyncio task started from the FastAPI lifespan,
* a configurable interval (``NEXA_MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS``,
  default 1 day),
* a ``scan_once`` coroutine that callers (and tests) can drive on demand,
* a ``kick_now`` helper for the operator-facing ``POST /-/check-updates-now``
  endpoint to short-circuit the next interval wait,
* idempotent ``start`` / ``stop`` so re-importing under uvicorn ``--reload``
  doesn't spawn duplicate tasks.

Failure model — strictly **notify-only** in v1:

* The checker calls :meth:`SkillInstaller.mark_update_checked` which stamps
  ``available_version`` + ``update_checked_at`` + flips the row's status to
  :class:`SkillStatus.OUTDATED` when a newer version exists.
* Even with ``NEXA_MARKETPLACE_AUTO_UPDATE_SKILLS=true`` the checker
  **never** silently re-installs a running skill. The flag is reserved for
  future "queue-an-update-job" wiring; today it's exposed in the structured
  scan counters so the UI can render a "ready to apply" badge.
* Network / 404 / parse failures are swallowed — a single skill failing to
  resolve should never break the loop for the rest of the catalog.

The whole module short-circuits to a no-op if either
``NEXA_CLAWHUB_ENABLED=false`` or
``NEXA_MARKETPLACE_PANEL_ENABLED=false`` — the same gate the marketplace
router uses.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.services.skills.clawhub_client import ClawHubClient
from app.services.skills.clawhub_models import InstalledSkill, SkillSource
from app.services.skills.installer import SkillInstaller

logger = logging.getLogger(__name__)


_MAX_CONCURRENT_PROBES = 4


class SkillUpdateChecker:
    """Periodic background checker for installed ClawHub skill updates."""

    def __init__(
        self,
        *,
        installer: SkillInstaller | None = None,
        client: ClawHubClient | None = None,
    ) -> None:
        self._installer = installer
        self._client = client
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._kick = asyncio.Event()

    # --- lifecycle ------------------------------------------------------

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        s = get_settings()
        if not bool(getattr(s, "nexa_clawhub_enabled", True)):
            logger.info("update_checker: clawhub disabled, not starting")
            return
        if not bool(getattr(s, "nexa_marketplace_panel_enabled", True)):
            logger.info("update_checker: marketplace panel disabled, not starting")
            return
        interval = int(
            getattr(s, "nexa_marketplace_update_check_interval_seconds", 86400) or 0
        )
        if interval <= 0:
            logger.info(
                "update_checker: interval=%s disables periodic checks (manual only)",
                interval,
            )
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.warning("update_checker.start called outside an event loop; skipping")
            return
        self._stop.clear()
        self._kick.clear()
        self._task = loop.create_task(self._run(), name="marketplace_update_checker")
        logger.info("update_checker: started (interval=%ss)", interval)

    async def stop(self) -> None:
        self._stop.set()
        # also wake the inner wait so we exit promptly without waiting an
        # entire interval for shutdown.
        self._kick.set()
        task = self._task
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await task
        self._task = None
        logger.info("update_checker: stopped")

    def kick_now(self) -> None:
        """Wake the loop so the next scan happens immediately (best-effort)."""
        self._kick.set()

    # --- main loop ------------------------------------------------------

    async def _run(self) -> None:
        s = get_settings()
        interval = max(
            60,
            int(getattr(s, "nexa_marketplace_update_check_interval_seconds", 86400) or 86400),
        )
        # Initial small jitter so process restarts don't dogpile the registry.
        await asyncio.sleep(min(15.0, interval / 60.0))
        while not self._stop.is_set():
            try:
                await self.scan_once()
            except Exception:  # noqa: BLE001
                logger.exception("update_checker: scan_once raised; continuing")
            self._kick.clear()
            try:
                await asyncio.wait_for(self._kick.wait(), timeout=interval)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # --- one scan pass --------------------------------------------------

    async def scan_once(self) -> dict[str, int]:
        """Probe every installed ClawHub skill once. Returns counters for tests.

        Counters:

        * ``scanned``       — number of skills probed
        * ``up_to_date``    — installed version matches remote latest
        * ``updates_found`` — remote has a newer version
        * ``unreachable``   — registry returned None / errored
        * ``skipped``       — non-clawhub source rows (local / builtin)
        """
        installer = self._installer or SkillInstaller()
        client = self._client or ClawHubClient()
        rows = installer.list_installed()
        counters = {
            "scanned": 0,
            "up_to_date": 0,
            "updates_found": 0,
            "unreachable": 0,
            "skipped": 0,
        }
        if not rows:
            return counters

        sem = asyncio.Semaphore(_MAX_CONCURRENT_PROBES)

        async def _probe(row: InstalledSkill) -> None:
            if row.source != SkillSource.CLAWHUB:
                counters["skipped"] += 1
                return
            async with sem:
                await self._probe_one(row, installer=installer, client=client, counters=counters)

        await asyncio.gather(*(_probe(r) for r in rows), return_exceptions=True)
        counters["scanned"] = len(rows) - counters["skipped"]
        return counters

    async def _probe_one(
        self,
        row: InstalledSkill,
        *,
        installer: SkillInstaller,
        client: ClawHubClient,
        counters: dict[str, int],
    ) -> None:
        try:
            remote = await client.get_skill_info(row.name)
        except Exception:  # noqa: BLE001
            logger.exception("update_checker: get_skill_info raised name=%s", row.name)
            counters["unreachable"] += 1
            return
        if remote is None:
            logger.info("update_checker: registry returned no info for %s", row.name)
            counters["unreachable"] += 1
            # Still stamp update_checked_at so the UI shows a fresh probe time.
            installer.mark_update_checked(
                row.name,
                available_version=row.available_version,
                checked_at=datetime.now(timezone.utc),
            )
            return
        try:
            installer.mark_update_checked(
                row.name,
                available_version=remote.version or None,
                checked_at=datetime.now(timezone.utc),
            )
        except Exception:  # noqa: BLE001
            logger.exception("update_checker: mark_update_checked failed name=%s", row.name)
            return
        if remote.version and remote.version != row.version:
            counters["updates_found"] += 1
            logger.info(
                "update_checker: update available name=%s installed=%s available=%s "
                "(notify-only; auto_apply=%s)",
                row.name,
                row.version,
                remote.version,
                bool(getattr(get_settings(), "nexa_marketplace_auto_update_skills", False)),
            )
        else:
            counters["up_to_date"] += 1


# --- module singleton ----------------------------------------------------


_checker: SkillUpdateChecker | None = None


def get_update_checker() -> SkillUpdateChecker:
    global _checker
    if _checker is None:
        _checker = SkillUpdateChecker()
    return _checker


__all__: list[str] = ["SkillUpdateChecker", "get_update_checker"]
# silence unused-import warning when type-checking sees `Any` only used in docstrings
_ = Any

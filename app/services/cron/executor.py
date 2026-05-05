"""Execute stored cron job actions (Phase 13)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.channel_gateway.slack_api import slack_chat_post_message
from app.services.cron.models import CronJob, JobActionType, JobStatus
from app.services.host_executor import execute_payload
from app.services.skills.plugin_registry import get_plugin_skill_registry
from app.services.telegram_outbound import send_telegram_message

logger = logging.getLogger("nexa.cron.executor")


class JobExecutor:
    """Execute scheduled cron jobs."""

    async def execute_job_by_id(self, job_id: str, *, store: Any) -> None:
        """Load job from store and run (async entrypoint for APScheduler)."""
        job = store.get(job_id)
        if not job or job.status != JobStatus.ACTIVE:
            logger.warning("cron skip job_id=%s (missing or not active)", job_id)
            return
        try:
            await self.execute_job(job)
            store.update_last_run(job_id, success=True)
            logger.info(
                "cron job ok id=%s name=%s runs=%s",
                job.id,
                job.name,
                job.run_count + 1,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("cron job failed id=%s", job_id)
            store.update_last_run(job_id, success=False, error=str(exc)[:2000])

    async def execute_job(self, job: CronJob) -> Any:
        """Run a loaded :class:`CronJob`."""
        if job.action_type == JobActionType.SKILL:
            return await self._execute_skill(job)
        if job.action_type == JobActionType.HOST_ACTION:
            return await self._execute_host_action(job)
        if job.action_type == JobActionType.CHANNEL_MESSAGE:
            return await self._execute_channel_message(job)
        if job.action_type == JobActionType.CHAIN:
            return await self._execute_chain(job)
        if job.action_type == JobActionType.WEBHOOK:
            return await self._execute_webhook(job)
        raise ValueError(f"Unknown action type: {job.action_type}")

    async def _execute_skill(self, job: CronJob) -> Any:
        registry = get_plugin_skill_registry()
        name = (job.action_payload.get("skill_name") or "").strip()
        if not name:
            raise ValueError("skill_name required in action_payload")
        if registry.get_skill(name) is None:
            raise ValueError(f"Skill not registered: {name}")
        result = await registry.execute_skill(name, dict(job.action_payload.get("input") or {}))
        if not result.success:
            raise RuntimeError(result.error or "skill failed")
        return result.output

    async def _execute_host_action(self, job: CronJob) -> Any:
        payload = dict(job.action_payload.get("payload") or job.action_payload)
        return await asyncio.to_thread(execute_payload, payload)

    async def _execute_channel_message(self, job: CronJob) -> Any:
        payload = job.action_payload
        channel = (payload.get("channel") or "").strip().lower()
        message = str(payload.get("message") or "").strip()
        if not message:
            raise ValueError("message required")
        if channel == "telegram":
            chat_id = str(payload.get("chat_id") or "").strip()
            if not chat_id:
                raise ValueError("chat_id required for telegram channel_message")
            ok = send_telegram_message(chat_id, message)
            if not ok:
                raise RuntimeError("telegram send failed")
            return {"channel": "telegram", "ok": True}
        if channel == "slack":
            channel_id = str(payload.get("channel_id") or "").strip()
            tok = (get_settings().slack_bot_token or "").strip()
            if not tok or not channel_id:
                raise ValueError("slack_bot_token and channel_id required")
            slack_chat_post_message(
                tok,
                channel=channel_id,
                text=message[:39000],
                thread_ts=(payload.get("thread_ts") or None),
                blocks=None,
                rate_limit_user_id=payload.get("rate_limit_user_id"),
            )
            return {"channel": "slack", "ok": True}
        raise ValueError(f"Unsupported channel_message channel: {channel}")

    async def _execute_chain(self, job: CronJob) -> Any:
        actions = job.action_payload.get("actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("chain requires actions: [{payload}, ...]")
        out: list[Any] = []
        for step in actions:
            if not isinstance(step, dict):
                raise ValueError("chain step must be object")
            out.append(await asyncio.to_thread(execute_payload, step))
        return out

    async def _execute_webhook(self, job: CronJob) -> Any:
        payload = job.action_payload
        url = (payload.get("url") or "").strip()
        if not url:
            raise ValueError("url required")
        method = (payload.get("method") or "POST").upper()
        headers = dict(payload.get("headers") or {})
        timeout = float(payload.get("timeout_seconds") or 60.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                r = await client.get(url, headers=headers)
            else:
                body = payload.get("json") if payload.get("json") is not None else payload.get("data")
                r = await client.post(url, headers=headers, json=body if isinstance(body, dict) else None)
            r.raise_for_status()
            return {"status_code": r.status_code, "text": r.text[:8000]}


__all__ = ["JobExecutor"]

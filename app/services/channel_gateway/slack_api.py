# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Slack Web API helpers (chat.postMessage)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.services.channel_gateway.rate_limit import acquire_outbound_slot
from app.services.channel_gateway.retry import outbound_with_retry

logger = logging.getLogger(__name__)


def slack_chat_post_message(
    bot_token: str,
    *,
    channel: str,
    text: str,
    thread_ts: str | None = None,
    blocks: list[dict[str, Any]] | None = None,
    rate_limit_user_id: str | None = None,
) -> dict[str, Any]:
    """
    https://api.slack.com/methods/chat.postMessage
    """
    acquire_outbound_slot(channel="slack", user_id=rate_limit_user_id)

    def _send() -> dict[str, Any]:
        body: dict[str, Any] = {
            "channel": channel,
            "text": text,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        if blocks:
            body["blocks"] = blocks
        r = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=30.0,
        )
        try:
            data = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack chat.postMessage non-json status=%s", r.status_code)
            raise RuntimeError("invalid_response") from exc
        if not data.get("ok"):
            err = data.get("error") or "slack_api_error"
            logger.info("slack chat.postMessage failed: %s", err)
            raise RuntimeError(err)
        return data

    return outbound_with_retry(channel="slack", operation="chat.postMessage", func=_send)


def slack_files_upload(
    bot_token: str,
    *,
    channel: str,
    content: bytes,
    filename: str,
    initial_comment: str | None = None,
    rate_limit_user_id: str | None = None,
) -> dict[str, Any]:
    """https://api.slack.com/methods/files.upload — binary image post when no public URL."""
    acquire_outbound_slot(channel="slack", user_id=rate_limit_user_id)

    def _upload() -> dict[str, Any]:
        data: dict[str, str] = {"channels": channel}
        if initial_comment:
            data["initial_comment"] = initial_comment[:4000]
        files = {"file": (filename, content)}
        r = httpx.post(
            "https://slack.com/api/files.upload",
            headers={"Authorization": f"Bearer {bot_token}"},
            data=data,
            files=files,
            timeout=120.0,
        )
        try:
            resp = r.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack files.upload non-json status=%s", r.status_code)
            raise RuntimeError("invalid_response") from exc
        if not resp.get("ok"):
            err = resp.get("error") or "slack_api_error"
            logger.info("slack files.upload failed: %s", err)
            raise RuntimeError(err)
        return resp

    return outbound_with_retry(channel="slack", operation="files.upload", func=_upload)

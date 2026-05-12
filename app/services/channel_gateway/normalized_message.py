# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Validate canonical normalized inbound payloads (Phase 12)."""

from __future__ import annotations

from typing import Any


def validate_normalized_message(msg: dict[str, Any]) -> None:
    """
    Ensure a normalized message matches the Channel Gateway contract.

    Raises :exc:`ValueError` if invalid (used by router and tests).
    """
    if not isinstance(msg, dict):
        raise ValueError("normalized_message must be a dict")
    ch = str(msg.get("channel") or "").strip()
    if not ch:
        raise ValueError("normalized_message.channel is required")
    cuid = str(msg.get("channel_user_id") or "").strip()
    if not cuid:
        raise ValueError("normalized_message.channel_user_id is required")
    uid = str(msg.get("user_id") or msg.get("app_user_id") or "").strip()
    if not uid:
        raise ValueError("normalized_message.user_id (or app_user_id) is required")
    meta = msg.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        raise ValueError("normalized_message.metadata must be a dict when present")
    att = msg.get("attachments")
    if att is not None and not isinstance(att, list):
        raise ValueError("normalized_message.attachments must be a list when present")

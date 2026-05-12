# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Merge channel gateway ContextVar into audit metadata (Phase 4 — trust lineage)."""

from __future__ import annotations

from typing import Any


def enrich_with_channel_origin(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    Add keys from ``get_channel_origin()`` into audit metadata without overwriting callers.

    When no origin is bound (Web cron paths, workers, tests), returns ``metadata`` unchanged
    (aside from copying to a mutable dict).
    """
    from app.services.channel_gateway.origin_context import get_channel_origin

    base = dict(metadata or {})
    origin = get_channel_origin()
    if not origin:
        return base
    for k, v in origin.items():
        if v is not None and k not in base:
            base[k] = v
    return base

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 45F — shrink autonomy payloads before gateway/provider paths."""

from __future__ import annotations

from typing import Any


def compress_context(ctx: dict[str, Any], *, max_string: int = 2400, max_list_items: int = 12) -> dict[str, Any]:
    """Remove redundancy from autonomy intel blobs destined for gateway extras."""
    out: dict[str, Any] = {}
    for k, v in (ctx or {}).items():
        if isinstance(v, str):
            out[k] = v[:max_string] + ("…" if len(v) > max_string else "")
        elif isinstance(v, list):
            out[k] = v[:max_list_items]
        elif isinstance(v, dict):
            out[k] = compress_context(dict(v), max_string=min(max_string, 1200), max_list_items=8)
        else:
            out[k] = v
    return out


__all__ = ["compress_context"]

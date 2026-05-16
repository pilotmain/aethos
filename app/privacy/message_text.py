# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Flatten LLM :class:`~app.services.llm.base.Message` lists for PII scanning (no raw logging)."""

from __future__ import annotations

import json
from typing import Any

from app.services.llm.base import Message


def flatten_messages_for_pii(messages: list[Message], *, max_chars: int = 120_000) -> str:
    """Concatenate textual message parts for deterministic PII detection."""
    parts: list[str] = []
    n = 0
    for m in messages:
        role = (m.role or "").strip()
        c = m.content
        if isinstance(c, str):
            chunk = f"[{role}]\n{c}\n"
        elif isinstance(c, list):
            try:
                chunk = f"[{role}]\n{json.dumps(c, ensure_ascii=False)[:50_000]}\n"
            except (TypeError, ValueError):
                chunk = f"[{role}]\n{str(c)[:50_000]}\n"
        else:
            chunk = f"[{role}]\n{str(c)}\n"
        parts.append(chunk)
        n += len(chunk)
        if n >= max_chars:
            break
    return "".join(parts)[:max_chars]

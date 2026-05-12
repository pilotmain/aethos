# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Optional standing orders from ``PULSE.md`` (OpenClaw-style continuity hint).

Read-only: never executes instructions in the file; only surfaces text to the user
when a workspace path is known and the file exists.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ~4k token budget for injection (rough chars; no tokenizer here).
_MAX_INJECT_CHARS = 12_000
_DEFAULT_NAMES = ("PULSE.md", "pulse.md")


def read_pulse_standing_orders(workspace_root: str | Path | None) -> str | None:
    """
    Return trimmed markdown from ``PULSE.md`` (or ``pulse.md``) under ``workspace_root``.

    **Re-read on every call** — no in-process cache — so edits during a session show up on the
    next operator turn.

    Returns ``None`` if missing, unreadable, or empty.
    """
    if workspace_root is None:
        return None
    root = Path(str(workspace_root)).expanduser()
    try:
        root = root.resolve()
    except OSError:
        return None
    if not root.is_dir():
        return None
    for name in _DEFAULT_NAMES:
        p = root / name
        if not p.is_file():
            continue
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("operator_pulse.read_failed path=%s err=%s", p, exc)
            return None
        raw = raw.strip()
        if not raw:
            return None
        if len(raw) > _MAX_INJECT_CHARS:
            raw = raw[: _MAX_INJECT_CHARS - 20] + "\n… (truncated)"
        return raw
    return None


def format_pulse_section(content: str) -> str:
    return "### Standing orders (PULSE.md)\n\n" + content.strip()


def get_pulse_context(workspace_root: str | Path | None, *, max_chars: int = 800) -> str:
    """
    Compact standing-orders block for prompts or summaries (OpenClaw-style memory hint).

    Separate from :func:`read_pulse_standing_orders` (full reply section); this caps
    more aggressively for token-light prefix use.
    """
    body = read_pulse_standing_orders(workspace_root)
    if not body:
        return ""
    cap = max(200, min(int(max_chars), _MAX_INJECT_CHARS))
    snippet = body if len(body) <= cap else body[: cap - 20].rstrip() + "\n… (truncated)"
    return f"\nStanding orders (PULSE.md):\n{snippet}\n"


def pulse_requests_no_production_deploy(pulse: str | None) -> bool:
    """
    Lightweight standing-order hint: skip production deploy when PULSE clearly forbids it.

    Does not parse natural language deeply — substring guardrails only.
    """
    if not (pulse or "").strip():
        return False
    pl = pulse.lower()
    needles = (
        "do not deploy",
        "never deploy",
        "no production deploy",
        "skip deploy",
        "do not ship to production",
    )
    return any(n in pl for n in needles)


__all__ = [
    "format_pulse_section",
    "get_pulse_context",
    "pulse_requests_no_production_deploy",
    "read_pulse_standing_orders",
]

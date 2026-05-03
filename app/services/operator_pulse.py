"""
Optional standing orders from ``PULSE.md`` (OpenClaw-style continuity hint).

Read-only: never executes instructions in the file; only surfaces text to the user
when a workspace path is known and the file exists.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_BYTES = 12_000
_DEFAULT_NAMES = ("PULSE.md", "pulse.md")


def read_pulse_standing_orders(workspace_root: str | Path | None) -> str | None:
    """
    Return trimmed markdown from ``PULSE.md`` (or ``pulse.md``) under ``workspace_root``.

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
        if len(raw) > _MAX_BYTES:
            raw = raw[: _MAX_BYTES - 20] + "\n… (truncated)"
        return raw
    return None


def format_pulse_section(content: str) -> str:
    return "### Standing orders (PULSE.md)\n\n" + content.strip()


__all__ = ["format_pulse_section", "read_pulse_standing_orders"]

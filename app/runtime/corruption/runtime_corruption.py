# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Move unusable ``aethos.json`` files aside and record quarantine metadata."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from app.core.paths import get_runtime_corruption_quarantine_dir
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso

_LOG = logging.getLogger("aethos.runtime.corruption")


def quarantine_corrupt_runtime_file(path: Path, *, reason: str) -> Path | None:
    """Rename ``path`` into ``corruption_quarantine/`` with a unique stem."""
    if not path.is_file():
        return None
    qdir = get_runtime_corruption_quarantine_dir()
    qdir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "")
    dest = qdir / f"aethos.corrupt.{ts}.json"
    if dest.exists():
        dest = qdir / f"aethos.corrupt.{ts}.{id(path):x}.json"
    try:
        shutil.move(str(path), str(dest))
    except OSError as exc:
        _LOG.warning("runtime.quarantine_move_failed %s", exc)
        return None
    orchestration_log.append_json_log(
        "runtime_corruption",
        "runtime_corruption_detected",
        quarantined_path=str(dest),
        reason=reason[:2000],
    )
    _LOG.warning("runtime.quarantined_corrupt_file dest=%s reason=%s", dest, reason[:500])
    return dest


def append_quarantine_record(st: dict[str, Any], *, key: str, payload: Any, note: str) -> None:
    """Move a bad top-level section into ``runtime_corruption_quarantine`` (preserves continuity)."""
    q = st.setdefault("runtime_corruption_quarantine", [])
    if not isinstance(q, list):
        st["runtime_corruption_quarantine"] = []
        q = st["runtime_corruption_quarantine"]
    q.append({"ts": utc_now_iso(), "key": str(key)[:256], "note": str(note)[:2000], "payload": payload})
    if len(q) > 80:
        del q[:-80]
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(st, "runtime_corruption_detected", key=key, note=note[:500])
    except Exception:
        pass
    orchestration_log.append_json_log(
        "runtime_corruption",
        "runtime_corruption_detected",
        key=key,
        note=note[:500],
    )

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Write verified JSON snapshots under ``~/.aethos/backups/``."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from app.core.paths import get_runtime_backups_dir, get_runtime_state_path
from app.orchestration import orchestration_log
from app.runtime.runtime_state import utc_now_iso

_LOG = logging.getLogger("aethos.runtime.backups")


def _bump_backup_metric(st: dict[str, Any]) -> None:
    m = st.setdefault("runtime_metrics", {})
    if isinstance(m, dict):
        m["runtime_backups_total"] = int(m.get("runtime_backups_total") or 0) + 1


def _note_last_backup(st: dict[str, Any], *, path: str, reason: str, bytes_written: int) -> None:
    rs = st.setdefault("runtime_resilience", {})
    if not isinstance(rs, dict):
        st["runtime_resilience"] = {}
        rs = st["runtime_resilience"]
    rs["last_backup"] = {"ts": utc_now_iso(), "path": path, "reason": reason, "bytes": bytes_written}


def backup_runtime_state_dict(st: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """
    Serialize ``st`` to ``~/.aethos/backups/aethos.<timestamp>.json`` after JSON round-trip verify.

    Mutates ``st`` only for resilience metadata + metrics (caller typically persists).
    """
    out: dict[str, Any] = {"ok": False, "reason": reason}
    try:
        raw = json.dumps(st, indent=2, sort_keys=False) + "\n"
        json.loads(raw)
    except (TypeError, ValueError) as exc:
        out["error"] = f"serialize_failed:{exc}"
        _LOG.warning("runtime.backup_serialize_failed %s", exc)
        return out

    dest_dir = get_runtime_backups_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "")
    dest = dest_dir / f"aethos.{ts}.json"
    if dest.is_file():
        dest = dest_dir / f"aethos.{ts}_{id(st):x}.json"
    try:
        dest.write_text(raw, encoding="utf-8")
    except OSError as exc:
        out["error"] = str(exc)
        _LOG.warning("runtime.backup_write_failed %s", exc)
        return out

    _bump_backup_metric(st)
    _note_last_backup(st, path=str(dest), reason=reason, bytes_written=len(raw.encode("utf-8")))
    orchestration_log.append_json_log(
        "runtime_backups",
        "runtime_backup_created",
        path=str(dest),
        reason=reason,
        bytes=len(raw.encode("utf-8")),
    )
    try:
        from app.runtime.events.runtime_events import emit_runtime_event

        emit_runtime_event(st, "runtime_backup_created", path=str(dest), reason=reason)
    except Exception:
        pass
    out["ok"] = True
    out["path"] = str(dest)
    return out


def snapshot_runtime_file_before_mutation(*, reason: str) -> dict[str, Any]:
    """Copy on-disk ``aethos.json`` to backups (when file exists). Does not read full JSON."""
    path = get_runtime_state_path()
    out: dict[str, Any] = {"ok": False, "reason": reason}
    if not path.is_file():
        out["skipped"] = True
        out["ok"] = True
        return out
    dest_dir = get_runtime_backups_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = utc_now_iso().replace(":", "").replace("-", "")
    dest = dest_dir / f"aethos.file.{ts}.json"
    try:
        shutil.copy2(path, dest)
    except OSError as exc:
        out["error"] = str(exc)
        return out
    orchestration_log.append_json_log(
        "runtime_backups",
        "runtime_backup_created",
        path=str(dest),
        reason=reason,
        mode="file_copy",
    )
    out["ok"] = True
    out["path"] = str(dest)
    return out

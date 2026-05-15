# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical ``~/.aethos/aethos.json`` read/write with atomic replace."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_workspace_root, get_runtime_state_path

_LOG = logging.getLogger("aethos.runtime")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utc_now_iso() -> str:
    """ISO-8601 UTC timestamp for runtime JSON fields."""
    return _utc_now()


def default_runtime_state(*, workspace_root: Path | None = None) -> dict[str, Any]:
    ws = workspace_root or get_aethos_workspace_root()
    return {
        "runtime_id": str(uuid.uuid4()),
        "created_at": _utc_now(),
        "last_started_at": None,
        "gateway": {
            "host": "0.0.0.0",
            "port": int(os.environ.get("AETHOS_RUNTIME_PORT") or os.environ.get("PORT") or "8010"),
            "running": False,
            "pid": None,
            "last_heartbeat": None,
        },
        "workspace": {"root": str(ws.resolve())},
        "sessions": [],
        "agents": [],
        "deployments": [],
        "channels": [],
        "tasks": [],
        "execution_queue": [],
        "long_running": [],
        "memory": {"enabled": True},
        "recovery": {"events": []},
    }


def load_runtime_state() -> dict[str, Any]:
    path = get_runtime_state_path()
    if not path.is_file():
        st = default_runtime_state()
        save_runtime_state(st)
        return st
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("root must be object")
        return data
    except Exception as exc:
        _LOG.warning("runtime_state.load_failed %s — resetting", exc)
        st = default_runtime_state()
        save_runtime_state(st)
        return st


def save_runtime_state(data: dict[str, Any]) -> None:
    path = get_runtime_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, sort_keys=False) + "\n"
    fd, tmp = tempfile.mkstemp(prefix="aethos-runtime-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def mark_gateway_stopped() -> None:
    try:
        st = load_runtime_state()
        gw = st.setdefault("gateway", {})
        gw["running"] = False
        gw["pid"] = None
        gw["last_heartbeat"] = _utc_now()
        save_runtime_state(st)
    except Exception as exc:
        _LOG.warning("runtime_state.mark_stopped_failed %s", exc)


def record_recovery_event(st: dict[str, Any], message: str) -> None:
    rec = st.setdefault("recovery", {})
    ev = rec.setdefault("events", [])
    if not isinstance(ev, list):
        ev = []
        rec["events"] = ev
    ev.append({"ts": _utc_now(), "message": message})
    if len(ev) > 50:
        del ev[:-50]

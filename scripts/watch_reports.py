# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Poll the reports directory and emit ui_update_event.json when files change (UI bridge)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

# Defaults match app/services/agent_runtime when NEXA_REPORTS_DIR is unset.
REPORTS_DIR = Path(os.getenv("NEXA_REPORTS_DIR", "")).expanduser()
if not str(REPORTS_DIR).strip():
    _root = Path(os.getenv("NEXA_WORKSPACE_ROOT", str(Path.home() / "nexa-projects"))).expanduser()
    REPORTS_DIR = _root / "reports"
STATE_FILE = Path(
    os.getenv("NEXA_REPORT_WATCH_STATE", str(Path.home() / "nexa-projects" / "memory" / "report_watch_state.json"))
).expanduser()


def snapshot_reports() -> dict[str, float]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    snap: dict[str, float] = {}
    for path in REPORTS_DIR.rglob("*"):
        if path.is_file():
            snap[str(path)] = path.stat().st_mtime
    return snap


def load_state() -> dict[str, float]:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_state(state: dict[str, float]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


def emit_update(changed_paths: list[str]) -> None:
    event_path = REPORTS_DIR / "ui_update_event.json"
    payload: dict[str, Any] = {
        "event": "reports.changed",
        "changed_paths": changed_paths,
        "updated_at": time.time(),
    }
    event_path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def main() -> None:
    interval = float(os.getenv("NEXA_REPORT_WATCH_INTERVAL", "2.0"))
    last = load_state()
    while True:
        current = snapshot_reports()
        changed = [p for p, m in current.items() if last.get(p) != m]
        if changed:
            emit_update(changed)
            save_state(current)
            last = current
        time.sleep(interval)


if __name__ == "__main__":
    main()

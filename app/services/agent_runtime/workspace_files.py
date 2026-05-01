"""Create and update workspace files under reports/config/memory with safe path rules."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.agent_runtime.defaults import (
    DEFAULT_AGENT_TOOLS_MANIFEST,
    default_agent_status_json,
    default_heartbeats_json,
    default_memory_json,
    default_mission_control_md,
    default_workspace_metadata,
)
from app.services.agent_runtime.paths import (
    agent_status_json_path,
    agent_tools_manifest_path,
    ensure_runtime_directories,
    heartbeats_json_path,
    memory_json_path,
    mission_control_md_path,
    reports_dir,
    timeline_jsonl_path,
    workspace_metadata_path,
)

logger = logging.getLogger(__name__)


def _atomic_write(path: Path, data: str | bytes, *, binary: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".nexa_", suffix=path.suffix)
    try:
        if binary:
            os.write(fd, data if isinstance(data, bytes) else data.encode())
        else:
            os.write(fd, data.encode() if isinstance(data, str) else data)
        os.close(fd)
        fd = -1
        os.replace(tmp, path)
    finally:
        try:
            if fd >= 0:
                os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    payload = json.dumps(obj, indent=2, sort_keys=True)
    _atomic_write(path, payload + "\n")


def read_json_file(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return dict(default)
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        logger.warning("read_json_file: could not parse %s", path)
        return dict(default)


def ensure_seed_files() -> None:
    ensure_runtime_directories()
    wm = workspace_metadata_path()
    if not wm.is_file():
        atomic_write_json(
            wm,
            default_workspace_metadata(
                workspace_mode=get_settings().nexa_workspace_mode,
            ),
        )
    man = agent_tools_manifest_path()
    if not man.is_file():
        atomic_write_json(man, dict(DEFAULT_AGENT_TOOLS_MANIFEST))
    mem = memory_json_path()
    if not mem.is_file():
        atomic_write_json(mem, default_memory_json())
    hb = heartbeats_json_path()
    if not hb.is_file():
        atomic_write_json(hb, default_heartbeats_json())
    mc = mission_control_md_path()
    if not mc.is_file():
        _atomic_write(mc, default_mission_control_md())
    st = agent_status_json_path()
    if not st.is_file():
        atomic_write_json(st, default_agent_status_json())
    tl = timeline_jsonl_path()
    if not tl.exists():
        tl.touch()


def read_workspace_metadata() -> dict[str, Any]:
    """Latest workspace_metadata.json from config dir (may be missing until seed)."""
    try:
        p = workspace_metadata_path()
        if not p.is_file():
            return {}
        return read_json_file(p, {})
    except Exception:  # noqa: BLE001
        logger.warning("read_workspace_metadata failed", exc_info=False)
        return {}


def merge_memory_spawn_record(
    *,
    spawn_group_id: str,
    goal: str,
    assignment_ids: list[int],
    user_id: str,
) -> None:
    ensure_seed_files()
    path = memory_json_path()
    data = read_json_file(path, default_memory_json())
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sg = data.setdefault("spawn_groups", {})
    sg[spawn_group_id] = {
        "goal": goal[:2000],
        "user_id": user_id,
        "assignment_ids": assignment_ids,
        "created_at": now,
    }
    for aid in assignment_ids:
        data.setdefault("assignments", {})[str(aid)] = {
            "spawn_group_id": spawn_group_id,
            "last_event": "spawn_created",
        }
    data["last_updated_at"] = now
    atomic_write_json(path, data)


def append_timeline_event(event: dict[str, Any]) -> None:
    ensure_seed_files()
    line = json.dumps(event, sort_keys=True)
    p = timeline_jsonl_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


ALLOWED_REPORT_FILES = frozenset({"mission_control.md", "ui_update_event.json"})


def safe_read_report_file(basename: str) -> str | None:
    """Read only whitelisted files under the resolved reports directory."""
    if basename not in ALLOWED_REPORT_FILES:
        return None
    root = reports_dir().resolve()
    target = (root / basename).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    try:
        return target.read_text()
    except OSError:
        return None


def read_mission_control_markdown() -> tuple[str, float | None]:
    ensure_seed_files()
    p = mission_control_md_path()
    mtime = p.stat().st_mtime if p.is_file() else None
    return p.read_text() if p.is_file() else "", mtime


def read_ui_update_event() -> dict[str, Any] | None:
    from app.services.agent_runtime.paths import ui_update_event_path

    ensure_seed_files()
    p = ui_update_event_path()
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return None

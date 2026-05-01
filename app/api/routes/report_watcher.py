"""Read-only access to workspace report files (mission_control.md, watcher events)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import get_settings
from app.core.security import get_valid_web_user_id
from app.services.agent_runtime.paths import mission_control_md_path, reports_dir, ui_update_event_path
from app.services.agent_runtime.workspace_files import ensure_seed_files, read_ui_update_event, safe_read_report_file

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/status")
def reports_status(
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Latest watcher event (if any) and mission_control.md mtime for UI polling."""
    _ = app_user_id  # scoped to authenticated user; paths are host-local
    s = get_settings()
    ensure_seed_files()
    mc = mission_control_md_path()
    mtime = mc.stat().st_mtime if mc.is_file() else None
    ev_path = ui_update_event_path()
    ev_mtime = ev_path.stat().st_mtime if ev_path.is_file() else None
    return {
        "enabled": bool(s.nexa_agent_tools_enabled or s.nexa_file_watcher_enabled),
        "reports_dir": str(reports_dir()),
        "mission_control_mtime": mtime,
        "ui_update_event_mtime": ev_mtime,
        "ui_event": read_ui_update_event(),
    }


@router.get("/mission-control")
def reports_mission_control(
    app_user_id: str = Depends(get_valid_web_user_id),
) -> dict:
    """Markdown content from reports/mission_control.md (whitelisted path only)."""
    _ = app_user_id
    ensure_seed_files()
    text = safe_read_report_file("mission_control.md") or ""
    mc = mission_control_md_path()
    mtime = mc.stat().st_mtime if mc.is_file() else None
    return {
        "markdown": text,
        "mission_control_mtime": mtime,
    }

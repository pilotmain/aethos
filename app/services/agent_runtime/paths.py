"""Resolve workspace reports/config/memory paths from settings."""

from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings


def workspace_root() -> Path:
    return Path(get_settings().nexa_workspace_root).expanduser().resolve()


def reports_dir() -> Path:
    s = get_settings()
    if s.nexa_reports_dir and str(s.nexa_reports_dir).strip():
        return Path(s.nexa_reports_dir).expanduser().resolve()
    return workspace_root() / "reports"


def config_dir() -> Path:
    s = get_settings()
    if s.nexa_config_dir and str(s.nexa_config_dir).strip():
        return Path(s.nexa_config_dir).expanduser().resolve()
    return workspace_root() / "config"


def memory_dir() -> Path:
    s = get_settings()
    if s.nexa_memory_dir and str(s.nexa_memory_dir).strip():
        return Path(s.nexa_memory_dir).expanduser().resolve()
    return workspace_root() / "memory"


def agent_tools_manifest_path() -> Path:
    return config_dir() / "agent_tools.json"


def workspace_metadata_path() -> Path:
    return config_dir() / "workspace_metadata.json"


def memory_json_path() -> Path:
    return memory_dir() / "memory.json"


def heartbeats_json_path() -> Path:
    return memory_dir() / "heartbeats.json"


def mission_control_md_path() -> Path:
    return reports_dir() / "mission_control.md"


def timeline_jsonl_path() -> Path:
    return reports_dir() / "timeline.jsonl"


def agent_status_json_path() -> Path:
    return reports_dir() / "agent_status.json"


def ui_update_event_path() -> Path:
    return reports_dir() / "ui_update_event.json"


def report_watch_state_path() -> Path:
    return memory_dir() / "report_watch_state.json"


def ensure_runtime_directories() -> None:
    for d in (reports_dir(), config_dir(), memory_dir()):
        d.mkdir(parents=True, exist_ok=True)

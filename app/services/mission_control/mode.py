# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control dashboard-mode detection — configuration, not executable spawn."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent_runtime.paths import config_dir, mission_control_md_path
from app.services.agent_runtime.workspace_files import _atomic_write, atomic_write_json, ensure_seed_files

logger = logging.getLogger(__name__)

# Strong signals: user is configuring the Mission Control UI / session, not spawning workers.
_DASHBOARD_PRIMARY: list[re.Pattern[str]] = [
    re.compile(r"(?is)\binitialize\s+dashboard\s+mode\b"),
    re.compile(r"(?is)\binitialize\s+mission\s+control\s+dashboard\s+mode\b"),
    re.compile(r"(?is)\bmission\s+control\s+dashboard\s+mode\b"),
    re.compile(r"(?is)\bdashboard\s+mode\s+for\s+(?:this\s+)?workspace\b"),
    re.compile(r"(?is)\blive\s+operational\s+command\s+center\b"),
    re.compile(r"(?is)\bstructure\s+responses\s+as\s+a\s+control\s+dashboard\b"),
    re.compile(r"(?is)\borganize\s+output\s+into\s+sections\b"),
    re.compile(r"(?is)\bwatchlist\s+behavior\b"),
    re.compile(r"(?is)\bvisual\s+formatting\b"),
    re.compile(r"(?is)\bmission\s+control\s+system\b"),
    re.compile(r"(?is)\btransform\s+this\s+session\b"),
    re.compile(r"(?is)\bwhen\s+i\s+give\s+a\s+mission\b.*\b(?:automatically\s+)?(?:create|assign)\b"),
]

_RE_STRIP_PATHS = re.compile(r"(?i)/[\w./\\-]+\.(?:md|json|txt|yaml|yml)\b")


def _strip_paths_for_detection(text: str) -> str:
    """Remove file paths so `/reports/mission_control.md` does not look like 'Mission Control'."""
    return _RE_STRIP_PATHS.sub(" ", text or "")


def is_mission_control_mode_prompt(text: str) -> bool:
    raw = _strip_paths_for_detection(text or "").strip()
    if not raw:
        return False
    for pat in _DASHBOARD_PRIMARY:
        if pat.search(raw):
            return True
    # Pair: "dashboard" + "mission control" (instructional, not path-only).
    if re.search(r"(?is)\bdashboard\s+mode\b", raw) and re.search(
        r"(?is)\bmission\s+control\b", raw
    ):
        return True
    return False


DEFAULT_WATCHLIST = [
    {"name": "AI Coding Agents", "score": 83, "trend": "rising", "tags": ["ai coding agents", "agentic coding", "cursor ai"]},
    {"name": "Local AI / On-device AI", "score": 82, "trend": "stable", "tags": ["local ai", "on-device ai"]},
    {"name": "AI Policy / Geopolitics", "score": 82, "trend": "rising", "tags": ["policy", "geopolitics", "ai safety"]},
]


def default_mission_control_mode_payload(*, created_by: str = "boss") -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "enabled": True,
        "response_style": "dashboard",
        "sections": ["active_missions", "agent_swarm", "watchlist", "reports", "memory"],
        "heartbeat_every_response": True,
        "watchlist_topics": list(DEFAULT_WATCHLIST),
        "created_by": created_by,
        "updated_at": now,
    }


def mission_control_mode_json_path() -> Path:
    return config_dir() / "mission_control_mode.json"


def dashboard_markdown_initial() -> str:
    """Template for /workspace/reports/mission_control.md when dashboard mode initializes."""
    return (
        "# Mission Control\n\n"
        "## 🧠 Active Missions\n\n"
        "No active missions.\n\n"
        "## 🤖 Agent Swarm\n\n"
        "| Agent | Role | Status |\n"
        "|---|---|---|\n"
        "| @boss | Orchestrator | online |\n"
        "| @researcher-pro | Research | standby |\n"
        "| @analyst-pro | Analysis | standby |\n"
        "| @qa | QA | standby |\n\n"
        "## 📊 Watchlist\n\n"
        "| Topic | Score | Trend |\n"
        "|---|---:|---|\n"
        "| AI Coding Agents | 83 | rising |\n"
        "| Local AI / On-device AI | 82 | stable |\n"
        "| AI Policy / Geopolitics | 82 | rising |\n\n"
        "## 📁 Reports\n\n"
        "No reports yet.\n\n"
        "## 💾 Memory\n\n"
        "Dashboard mode initialized.\n"
    )


def persist_dashboard_mode_files(*, created_by: str = "boss") -> None:
    ensure_seed_files()
    cfg = mission_control_mode_json_path()
    atomic_write_json(cfg, default_mission_control_mode_payload(created_by=created_by))
    mc = mission_control_md_path()
    _atomic_write(mc, dashboard_markdown_initial())


SPLIT_MESSAGE = (
    "Dashboard mode initialized. Send the mission task next.\n\n"
    "No agent sessions were spawned."
)


def format_dashboard_mode_initialized_reply(*, mixed_split: bool = False) -> str:
    if mixed_split:
        return (
            "# Mission Control Dashboard Mode\n\n"
            "Status: **initialized** (configuration only)\n\n"
            "🧠 **Active Missions**\n"
            "No agent sessions were spawned.\n\n"
            "📁 **Reports**\n"
            "`mission_control.md` initialized.\n\n"
            "💾 **Memory**\n"
            "Dashboard mode saved.\n\n"
            "---\n\n"
            + SPLIT_MESSAGE
        )

    return (
        "# Mission Control Dashboard Mode\n\n"
        "Status: **initialized**\n\n"
        "🧠 **Active Missions**\n"
        "No active missions.\n\n"
        "🤖 **Agent Swarm**\n"
        "- @boss — online\n"
        "- @researcher-pro — standby\n"
        "- @analyst-pro — standby\n"
        "- @qa — standby\n\n"
        "📊 **Watchlist**\n"
        "- AI Coding Agents — 83 — rising\n"
        "- Local AI / On-device AI — 82 — stable\n"
        "- AI Policy / Geopolitics — 82 — rising\n\n"
        "📁 **Reports**\n"
        "`mission_control.md` initialized.\n\n"
        "💾 **Memory**\n"
        "Dashboard mode saved.\n\n"
        "**No agent sessions were spawned.**"
    )


def _dashboard_execute_mission_hint(text: str) -> bool:
    """True when user mentions executing a mission without a complete bounded spawn doc."""
    return bool(
        re.search(
            r"(?is)\b(?:execute|run)\b\s+(?:a\s+|the\s+|robotics\s+)?mission\b",
            text or "",
        )
    )


def handle_mission_control_dashboard_turn(
    db: Session,
    user_id: str,
    message: str,
    *,
    inner_mission: dict[str, Any] | None,
) -> str:
    """
    Persist dashboard config + mission_control.md; reply depends on whether a structured
    bounded mission was also detected (mixed paste → separation message).
    """
    _ = db  # audit hook reserved
    uid = (user_id or "").strip()[:64]
    try:
        persist_dashboard_mode_files(created_by="boss")
    except Exception as exc:  # noqa: BLE001
        logger.exception("persist_dashboard_mode_files: %s", exc)
        return f"Could not save Mission Control dashboard mode files: {exc!s}"[:2000]

    mixed = bool(inner_mission) or _dashboard_execute_mission_hint(message)
    body = format_dashboard_mode_initialized_reply(mixed_split=mixed)
    # Lightweight audit trail in logs (no new audit event type required for MVP).
    logger.info(
        "mission_control_dashboard_mode user_id=%s mixed_structured_mission=%s",
        uid[:32],
        mixed,
    )
    return body

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Universal chat response layout helpers (opt-in via Settings ``nexa_response_format``)."""

from __future__ import annotations

from enum import Enum
from typing import Any


class ResponseType(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PROGRESS = "progress"
    INFO = "info"
    WARNING = "warning"
    DEPLOYMENT = "deployment"
    METRICS = "metrics"
    STATUS = "status"


# Intent slug → (display title, response kind). Extend without touching formatter core logic.
_INTENT_PRESENTATION: dict[str, tuple[str, ResponseType]] = {
    "observability_dashboard": ("Observability", ResponseType.METRICS),
    "goal_completed": ("Goal run", ResponseType.SUCCESS),
    "goal_orchestration": ("Goal run", ResponseType.SUCCESS),
    "react_app_completed": ("React app", ResponseType.SUCCESS),
    "react_app_error": ("React app", ResponseType.ERROR),
    "batch_completed": ("Batch files", ResponseType.SUCCESS),
    "file_read": ("File", ResponseType.INFO),
    "file_read_error": ("File", ResponseType.ERROR),
    "host_executor": ("Host action", ResponseType.INFO),
    "inter_agent_chain": ("Agents", ResponseType.INFO),
    "status_dashboard": ("Status", ResponseType.STATUS),
    "config_query": ("Configuration", ResponseType.INFO),
    "operator_execution": ("Operator", ResponseType.SUCCESS),
    "execution_loop": ("Execution", ResponseType.INFO),
    "deployment_complete": ("Deployment", ResponseType.DEPLOYMENT),
    "deployment_failed": ("Deployment", ResponseType.ERROR),
}


class ResponseFormatter:
    """Generic Markdown-shaped formatter (works for web + Telegram renderers)."""

    EMOJIS: dict[ResponseType, str] = {
        ResponseType.SUCCESS: "✅",
        ResponseType.ERROR: "❌",
        ResponseType.PROGRESS: "🔄",
        ResponseType.INFO: "ℹ️",
        ResponseType.WARNING: "⚠️",
        ResponseType.DEPLOYMENT: "🚀",
        ResponseType.METRICS: "📊",
        ResponseType.STATUS: "💓",
    }

    @classmethod
    def format(
        cls,
        title: str,
        response_type: ResponseType,
        *,
        items: list[dict[str, Any]] | None = None,
        sections: dict[str, Any] | None = None,
        urls: dict[str, str] | None = None,
        status: str | None = None,
        tip: str | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
    ) -> str:
        emoji = cls.EMOJIS.get(response_type, "📌")
        lines: list[str] = [f"{emoji} **{title.strip().upper()}**", ""]

        if progress_current is not None and progress_total is not None and progress_total > 0:
            pct = min(100, int((progress_current / progress_total) * 100))
            bar_len = 20
            filled = int(bar_len * progress_current / progress_total)
            bar = "█" * filled + "░" * (bar_len - filled)
            lines.append(f"Progress: [{bar}] {pct}%")
            lines.append(f"Step {progress_current} of {progress_total}")
            lines.append("")

        if items:
            for item in items:
                mark = cls._status_mark(item.get("status"))
                label = str(item.get("label", "") or "")
                value = str(item.get("value", "") or "")
                if item.get("is_url"):
                    lines.append(f"• {mark} **{label}:** [{value}]({value})")
                else:
                    lines.append(f"• {mark} **{label}:** {value}")

        if sections:
            for section_title, content in sections.items():
                lines.append("")
                lines.append(f"**{section_title}**")
                if isinstance(content, list):
                    for it in content:
                        lines.append(f"  • {it}")
                elif isinstance(content, dict):
                    for k, v in content.items():
                        lines.append(f"  • **{k}:** {v}")
                else:
                    lines.append(f"  {content}")

        if urls:
            lines.append("")
            lines.append("**Links**")
            for name, url in urls.items():
                ok = bool(url and str(url).startswith(("http://", "https://")))
                mark = cls.EMOJIS[ResponseType.SUCCESS] if ok else "⚠️"
                lines.append(f"• **{name}:** {url} {mark}")

        if status:
            lines.append("")
            lines.append(f"**Status:** {cls.EMOJIS[ResponseType.SUCCESS]} {status}")

        if tip:
            lines.append("")
            lines.append(f"💡 {tip}")

        return "\n".join(lines).strip()

    @classmethod
    def format_progress_update(
        cls,
        step: str,
        current: int,
        total: int,
        *,
        details: str | None = None,
    ) -> str:
        lines = [
            f"{cls.EMOJIS[ResponseType.PROGRESS]} **{step.strip()}**",
            "",
            f"Progress: step {current} of {total}",
        ]
        if details:
            lines.append(f"📋 {details}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _status_mark(raw: str | None) -> str:
        if raw == "success":
            return "✅"
        if raw == "failed":
            return "❌"
        if raw == "pending":
            return "⏳"
        if raw == "active":
            return "🟢"
        return "•"


def looks_chat_preformatted(text: str) -> bool:
    """True when the assistant body already has substantial Markdown / banners."""
    s = (text or "").lstrip()
    if not s:
        return True
    if s.startswith(("# ", "## ", "### ", "**", "> ", "- ", "• ", "```")):
        return True
    head = s.split("\n", 1)[0]
    if len(head) > 2 and ord(head[0]) > 127 and head[1] == " ":
        return True
    return False


def apply_gateway_response_style(intent: str | None, text: str) -> str:
    """
    Optionally wrap plain replies in a consistent banner (beautiful mode only).

    Default ``simple`` / ``raw`` leaves text unchanged.
    """
    from app.core.config import get_settings

    s = get_settings()
    mode = str(getattr(s, "nexa_response_format", "simple") or "simple").lower().strip()
    if mode in ("raw", "simple", ""):
        return text
    if mode != "beautiful":
        return text
    if looks_chat_preformatted(text):
        return text

    raw_intent = (intent or "").strip() or "reply"
    tpl = _INTENT_PRESENTATION.get(raw_intent)
    if tpl:
        title, rt = tpl
    else:
        title = raw_intent.replace("_", " ").title() if raw_intent != "reply" else "AethOS"
        rt = ResponseType.INFO

    # Single section preserves full assistant body without per-scenario branching.
    return ResponseFormatter.format(
        title,
        rt,
        sections={"Message": text.strip()},
    )


__all__ = [
    "ResponseFormatter",
    "ResponseType",
    "apply_gateway_response_style",
    "looks_chat_preformatted",
]

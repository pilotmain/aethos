"""Pro auto-dev policy — extends OSS gates without bypassing safety."""

from __future__ import annotations

from typing import Any


def should_execute(task: dict[str, Any], context: dict[str, Any]) -> bool:
    """
    When ``context["core_allowed"]`` is True, OSS already approved — always pass through.

    Otherwise Pro may allow a **narrow** superset: e.g. medium-risk ``stuck_dev`` with clear error signals.
    """
    if context.get("core_allowed"):
        return True
    intent = str((task or {}).get("intent") or "")
    risk = str((task or {}).get("risk") or "low")
    if risk == "high":
        return False
    if (task or {}).get("workspace_count") != 1:
        return False
    if intent == "stuck_dev" and risk == "medium":
        text = str((task or {}).get("user_text") or "").lower()
        if any(k in text for k in ("error", "fail", "trace", "exception", "panic")):
            return True
    return False


__all__ = ["should_execute"]

"""Budget toggles without LLM / :class:`~app.services.llm.base.Message` imports (import-cycle safe)."""

from __future__ import annotations

from app.core.config import get_settings


def budget_enabled() -> bool:
    s = get_settings()
    return bool(getattr(s, "nexa_budget_enabled", True))


__all__ = ["budget_enabled"]

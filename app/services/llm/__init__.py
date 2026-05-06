"""
Phase 11 — multi-provider LLM layer (registry + primary completion for :mod:`app.services.llm_service`).

Remote gateway tool missions continue to use :func:`app.services.providers.gateway.call_provider`.

Public symbols are loaded lazily so ``from app.services.llm.base import Message`` does not
eager-import :mod:`app.services.llm.completion` (avoids a cycle with :mod:`app.services.budget.hooks`).
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "get_llm",
    "primary_complete_messages",
    "primary_complete_raw",
    "primary_complete_streaming",
    "providers_available",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from app.services.llm import completion

        return getattr(completion, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

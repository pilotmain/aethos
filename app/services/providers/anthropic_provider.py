"""Anthropic — reserved; no network calls in Phase 4."""

from __future__ import annotations

from typing import Any


def call_anthropic(_payload: dict[str, Any]) -> dict[str, Any]:
    raise NotImplementedError("Anthropic provider is not wired in Phase 4 (use provider gateway only).")

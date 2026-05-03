"""Image / multimodal routing — privacy-gated MVP."""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings


def route_multimodal_image(
    *,
    metadata: dict[str, Any],
    user_id: str | None,
) -> dict[str, Any]:
    """
    Returns a structured result; does not ship bytes off-machine unless policy allows.

    When strict privacy is on and no local model path exists, returns an explicit unsupported message.
    """
    s = get_settings()
    strict = bool(getattr(s, "nexa_strict_privacy_mode", False))
    local_first = bool(getattr(s, "nexa_local_first", False))
    ollama = bool(getattr(s, "nexa_ollama_enabled", False))
    if strict and not (local_first and ollama):
        return {
            "ok": False,
            "reason": "multimodal_disabled_strict_privacy",
            "detail": "Configure local-first routing (e.g. Ollama) before enabling vision.",
            "metadata_keys": sorted(metadata.keys())[:40],
        }
    return {
        "ok": True,
        "reason": "multimodal_stub",
        "note": "Vision decode not wired; metadata accepted for future routing.",
        "user_id": (user_id or "")[:64],
    }


__all__ = ["route_multimodal_image"]

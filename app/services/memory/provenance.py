"""Memory entry provenance fields (stored inside ``value_json`` / client payloads)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

SourceKind = Literal["chat", "mission", "file", "email", "manual"]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def enrich_memory_value(
    value: dict[str, Any],
    *,
    source: SourceKind,
    source_ref: str | None = None,
    confidence: float = 1.0,
) -> dict[str, Any]:
    """Attach provenance keys without removing existing content."""
    out = dict(value)
    out.setdefault("source", source)
    if source_ref:
        out.setdefault("source_ref", str(source_ref)[:2000])
    out.setdefault("created_at", _utc_iso())
    out["confidence"] = max(0.0, min(1.0, float(confidence)))
    out["version"] = int(out.get("version") or 1)
    return out


__all__ = ["enrich_memory_value"]

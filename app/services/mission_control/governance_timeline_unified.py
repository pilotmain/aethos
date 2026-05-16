# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Authoritative unified governance timeline with deduplication (Phase 3 Step 14)."""

from __future__ import annotations

from typing import Any

from app.services.runtime_governance import build_governance_timeline


def _dedupe_key(entry: dict[str, Any]) -> str:
    return "|".join(str(entry.get(k) or "") for k in ("at", "kind", "who", "what"))


def build_unified_governance_timeline(truth: dict[str, Any] | None = None, *, limit: int = 40) -> dict[str, Any]:
    """Single timeline — merges governance sources without duplicate keys."""
    truth = truth or {}
    base = build_governance_timeline(limit=limit + 16)
    entries = list(base.get("timeline") or [])

    for rec in ((truth.get("runtime_recommendations") or {}).get("recommendations") or [])[:4]:
        if isinstance(rec, dict):
            entries.append(
                {
                    "at": None,
                    "kind": "recommendation",
                    "who": "runtime intelligence",
                    "what": str(rec.get("message") or "")[:120],
                    "confidence": rec.get("confidence"),
                }
            )

    for sig in ((truth.get("operational_risk") or {}).get("risk_signals") or [])[:3]:
        if isinstance(sig, dict):
            entries.append(
                {
                    "at": None,
                    "kind": "risk",
                    "who": "workspace",
                    "what": f"{sig.get('kind')} ({sig.get('severity')})",
                }
            )

    for esc in ((truth.get("runtime_escalations") or {}).get("active_escalations") or [])[:6]:
        if isinstance(esc, dict):
            entries.append(
                {
                    "at": None,
                    "kind": "escalation",
                    "who": esc.get("source") or "runtime",
                    "what": f"{esc.get('type')}: {esc.get('severity')}",
                    "severity": esc.get("severity"),
                }
            )

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        key = _dedupe_key(e)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    deduped.sort(key=lambda e: str(e.get("at") or ""), reverse=True)
    windowed = deduped[:limit]
    return {
        "timeline": windowed,
        "entry_count": len(windowed),
        "deduped_from": len(entries),
        "authoritative": True,
        "summary": base.get("summary"),
        "searchable_kinds": sorted({e.get("kind") for e in windowed if e.get("kind")}),
    }

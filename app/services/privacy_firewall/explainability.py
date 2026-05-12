# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Human-readable explanations for privacy detection outcomes (Phase 19)."""

from __future__ import annotations

from typing import Any, Mapping


def explain_detection(findings: Mapping[str, Any]) -> dict[str, Any]:
    """
    Summarize *why* detectors fired — for integrity alerts and Mission Control UI.

    Returns keys aligned with stored alert JSON: ``reason``, ``pattern``
    (alias ``matched_pattern``), ``confidence``.
    """
    conf = findings.get("confidence")
    if conf is None:
        conf = "low"
    secrets = list(findings.get("secrets") or [])
    pii = list(findings.get("pii") or [])
    matched: list[str] = [*(str(x) for x in secrets), *(str(x) for x in pii)]
    parts: list[str] = []
    if secrets:
        parts.append(
            "Secret-shaped material matched outbound safety rules "
            f"({', '.join(secrets)})."
        )
    if pii:
        parts.append(f"Personally identifiable information categories matched: {', '.join(pii)}.")
    reason = " ".join(parts) if parts else "No sensitive patterns matched under current detection mode."
    pattern_summary = ", ".join(matched) if matched else "none"
    return {
        "reason": reason,
        "matched_pattern": pattern_summary,
        "pattern": pattern_summary,
        "confidence": conf,
    }


__all__ = ["explain_detection"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Correlation keys for attributing audits to workflows and runs.

All trust-related audits should merge these keys into ``metadata_json`` when known.
Stable keys: ``workflow_id``, ``run_id``, ``execution_id`` (strings, truncated).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

CORRELATION_KEYS: frozenset[str] = frozenset(("workflow_id", "run_id", "execution_id"))


@dataclass(frozen=True)
class TrustCorrelation:
    workflow_id: str | None = None
    run_id: str | None = None
    execution_id: str | None = None

    def as_metadata(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.workflow_id and str(self.workflow_id).strip():
            out["workflow_id"] = str(self.workflow_id).strip()[:256]
        if self.run_id and str(self.run_id).strip():
            out["run_id"] = str(self.run_id).strip()[:256]
        if self.execution_id and str(self.execution_id).strip():
            out["execution_id"] = str(self.execution_id).strip()[:256]
        return out


def correlation_from_payload(payload: dict[str, Any] | None) -> dict[str, str]:
    """Extract correlation fields from host/orchestrator payloads (optional keys)."""
    p = payload or {}
    tc = TrustCorrelation(
        workflow_id=p.get("workflow_id"),
        run_id=p.get("run_id"),
        execution_id=p.get("execution_id"),
    )
    return tc.as_metadata()


def merge_correlation(metadata: dict[str, Any] | None, extra: dict[str, Any] | None) -> dict[str, Any]:
    """Merge correlation dicts into metadata (non-destructive copy)."""
    base = dict(metadata or {})
    if extra:
        for k, v in extra.items():
            if k in CORRELATION_KEYS and v is not None and str(v).strip():
                base[k] = str(v).strip()[:256]
    return base


def warn_missing_correlation(
    payload: dict[str, Any] | None,
    *,
    boundary: str,
    logger: logging.Logger | None = None,
    hint: str | None = None,
) -> None:
    """
    Prefer workflow_id **or** execution_id (run_id also counts) on privileged payloads.

    Logs at WARNING only — does not fail execution; use during integration to close gaps.
    """
    log = logger or logging.getLogger(__name__)
    p = payload or {}
    if (p.get("workflow_id") or "").strip() or (p.get("execution_id") or "").strip():
        return
    if (p.get("run_id") or "").strip():
        return
    extra = f" hint={hint}" if hint else ""
    log.warning(
        "trust.correlation_gap boundary=%s missing workflow_id/execution_id/run_id%s",
        boundary[:64],
        extra[:200],
    )

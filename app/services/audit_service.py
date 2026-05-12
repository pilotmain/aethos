# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Append-only audit log for dev jobs and policy events."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.services.channel_gateway.audit_integration import enrich_with_channel_origin
from app.services.trust_audit_correlation import CORRELATION_KEYS, merge_correlation

logger = logging.getLogger(__name__)


def audit(
    db: Session,
    *,
    event_type: str,
    actor: str,
    message: str,
    user_id: str | None = None,
    job_id: int | None = None,
    metadata: dict[str, Any] | None = None,
    workflow_id: str | None = None,
    run_id: str | None = None,
    execution_id: str | None = None,
    organization_id: str | None = None,
) -> AuditLog:
    md = merge_correlation(
        metadata,
        {k: v for k, v in {"workflow_id": workflow_id, "run_id": run_id, "execution_id": execution_id}.items() if v},
    )
    oid = (organization_id or "").strip()[:64]
    if oid:
        md = merge_correlation(md, {"organization_id": oid})
    md = enrich_with_channel_origin(md)
    for k in list(md.keys()):
        if k in CORRELATION_KEYS and md[k] is not None:
            md[k] = str(md[k]).strip()[:256]

    row = AuditLog(
        user_id=user_id,
        job_id=job_id,
        event_type=event_type[:64],
        actor=actor[:32],
        message=(message or "")[:4000],
        metadata_json=md,
    )
    db.add(row)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("audit log commit failed: %s", exc)
        raise
    db.refresh(row)
    return row

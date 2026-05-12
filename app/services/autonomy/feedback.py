# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 44F — persist structured feedback for autonomy learning loops."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.autonomy import NexaTaskFeedback


def record_task_feedback(
    db: Session,
    *,
    user_id: str,
    task_id: str,
    outcome: str,
    reason: str = "",
    meta: dict[str, Any] | None = None,
) -> NexaTaskFeedback:
    row = NexaTaskFeedback(
        id=str(uuid.uuid4()),
        user_id=(user_id or "").strip()[:128],
        task_id=(task_id or "").strip()[:128],
        outcome=(outcome or "").strip()[:16],
        reason=(reason or "").strip()[:20_000],
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


__all__ = ["record_task_feedback"]

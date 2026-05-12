# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.services.audit_service import audit
from app.services.checkin_service import CheckInService
from app.services.nexa_safety_policy import policy_audit_metadata


def process_due_checkins() -> dict:
    db: Session = SessionLocal()
    try:
        audit(
            db,
            event_type="safety.worker.invoke",
            actor="followup_worker",
            message="process_due_checkins",
            metadata=policy_audit_metadata(),
        )
        service = CheckInService()
        due = service.process_due(db)
        return {"processed": len(due), "checkin_ids": [row.id for row in due]}
    finally:
        db.close()

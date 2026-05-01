from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.audit_service import audit
from app.services.checkin_service import CheckInService
from app.services.handoff_tracking_service import HandoffTrackingService
from app.services.nexa_safety_policy import policy_audit_metadata
from app.services.system_health_service import get_system_health
from app.workers.operator_supervisor import process_supervisor_cycle

router = APIRouter(prefix="/internal", tags=["internal"])
service = CheckInService()
handoff_service = HandoffTrackingService()


@router.post("/process-due-checkins")
def process_due_checkins(db: Session = Depends(get_db)):
    audit(
        db,
        event_type="safety.internal.invoke",
        actor="internal",
        message="process-due-checkins",
        metadata=policy_audit_metadata(),
    )
    due = service.process_due(db)
    return {"processed": len(due), "checkin_ids": [row.id for row in due]}


@router.post("/process-job-handoffs")
def process_job_handoffs(db: Session = Depends(get_db)):
    audit(
        db,
        event_type="safety.internal.invoke",
        actor="internal",
        message="process-job-handoffs",
        metadata=policy_audit_metadata(),
    )
    rows = handoff_service.process_waiting_handoffs(db)
    return {"processed": len(rows), "job_ids": [row.id for row in rows]}


@router.post("/process-supervisor-cycle")
def process_operator_cycle():
    return process_supervisor_cycle()


@router.get("/system-health")
def system_health():
    return get_system_health()

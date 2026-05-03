from __future__ import annotations

import uuid

from app.models.dev_runtime import NexaDevRun
from app.services.run_steering import cancel_run, edit_run_goal, pause_run, resume_run


def test_run_steering_cancel_and_goal(db_session) -> None:
    uid = f"rs_{uuid.uuid4().hex[:10]}"
    rid = f"dr_{uuid.uuid4().hex[:12]}"
    run = NexaDevRun(
        id=rid,
        user_id=uid,
        workspace_id="ws",
        goal="original",
        status="queued",
    )
    db_session.add(run)
    db_session.commit()

    assert pause_run(db_session, rid, uid) is not None
    r2 = db_session.get(NexaDevRun, rid)
    assert r2 and r2.status == "paused"

    assert resume_run(db_session, rid, uid) is not None
    r3 = db_session.get(NexaDevRun, rid)
    assert r3 and r3.status == "queued"

    assert edit_run_goal(db_session, rid, uid, "new goal") is not None
    assert db_session.get(NexaDevRun, rid).goal == "new goal"

    assert cancel_run(db_session, rid, uid) is not None
    assert db_session.get(NexaDevRun, rid).status == "cancelled"

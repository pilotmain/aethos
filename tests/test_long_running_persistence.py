# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 42 — DB-backed long-running sessions survive tick scheduling."""

from __future__ import annotations

import uuid

from app.services.agents.long_running import tick_eligible_db_sessions, upsert_db_session


def test_upsert_and_tick_db_session(db_session) -> None:
    uid = f"lr_persist_{uuid.uuid4().hex[:12]}"
    sk = f"sess_{uuid.uuid4().hex[:10]}"
    upsert_db_session(
        db_session,
        user_id=uid,
        session_key=sk,
        goal="keep working",
        interval_seconds=30,
        state={"note": "x"},
    )
    out = tick_eligible_db_sessions(db_session)
    ours = [x for x in out if x.get("user_id") == uid and x.get("session_key") == sk]
    assert len(ours) == 1
    assert ours[0].get("iteration") == 1
    out2 = tick_eligible_db_sessions(db_session)
    ours2 = [x for x in out2 if x.get("user_id") == uid and x.get("session_key") == sk]
    assert len(ours2) == 0

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.mission_control_first_run import build_mission_control_first_run


def test_guided_tour_topics_present() -> None:
    out = build_mission_control_first_run({})
    tour = out["mission_control_first_run"]["guided_tour"]
    topics = tour["topics"]
    ids = {t["id"] for t in topics}
    assert "office" in ids
    assert "governance" in ids
    assert "recovery" in ids

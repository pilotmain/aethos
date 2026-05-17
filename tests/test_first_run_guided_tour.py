# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.mission_control_first_run import build_mission_control_first_run


def test_first_run_guided_tour_topics() -> None:
    blob = build_mission_control_first_run({})
    tour = blob["mission_control_first_run"]["guided_tour"]
    topics = tour["topics"]
    assert len(topics) >= 7
    ids = {t["id"] for t in topics}
    assert "office" in ids
    assert "workers" in ids
    assert "providers" in ids

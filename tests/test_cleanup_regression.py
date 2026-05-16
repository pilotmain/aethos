# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_intelligence import build_mission_control_runtime
from app.services.mission_control.runtime_panels import build_runtime_panels


def test_runtime_and_panels_share_health(db_session) -> None:
    rt = build_mission_control_runtime(db_session, user_id="cleanup_reg_user")
    panels = build_runtime_panels("cleanup_reg_user")
    assert panels["runtime_health"] == rt["runtime_health"]

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — scheduler dev job kinds."""

from __future__ import annotations

import json

from app.services.scheduler.dev_jobs import DEFAULT_GOALS, parse_dev_mission_payload


def test_parse_nightly_test_payload() -> None:
    raw = json.dumps(
        {"type": "nightly_test", "workspace_id": "w1", "goal": "", "preferred_agent": "local_stub"}
    )
    p = parse_dev_mission_payload(raw)
    assert p is not None
    assert p["type"] == "nightly_test"


def test_default_goal_mapping() -> None:
    assert "nightly_test" in DEFAULT_GOALS

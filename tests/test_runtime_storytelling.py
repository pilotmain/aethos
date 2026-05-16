# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_storytelling import build_runtime_stories
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_stories_on_truth() -> None:
    truth = build_runtime_truth(user_id=None)
    stories = truth.get("runtime_stories") or {}
    assert stories.get("data_derived") is True
    assert "governance_trust" in (stories.get("stories") or {})


def test_stories_shape() -> None:
    out = build_runtime_stories({})
    assert isinstance(out.get("stories"), dict)

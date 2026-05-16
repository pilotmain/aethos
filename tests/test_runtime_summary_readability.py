# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_summary_readability import (
    build_readable_summaries,
    humanize_provider_action,
    humanize_repair_summary,
)
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_humanize_helpers_non_empty() -> None:
    assert "Repair" in humanize_repair_summary({"status": "active", "project_id": "p1"})
    assert "vercel" in humanize_provider_action({"provider": "vercel", "action": "deploy"}).lower()


def test_truth_readable_summaries() -> None:
    truth = build_runtime_truth(user_id=None)
    summaries = truth.get("readable_summaries") or build_readable_summaries(truth)
    assert "runtime_health" in summaries
    assert isinstance(summaries.get("repairs"), list)
    assert isinstance(summaries.get("provider_actions"), list)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import infer_category_severity, normalize_runtime_event


def test_repair_event_category() -> None:
    cat, sev = infer_category_severity("repair_started")
    assert cat == "repair"
    assert sev == "info"


def test_normalized_shape() -> None:
    row = normalize_runtime_event("brain_selected", payload={"provider": "openai"})
    assert row["event_type"] == "brain_selected"
    assert row["category"] == "brain"
    assert row["correlation_id"]

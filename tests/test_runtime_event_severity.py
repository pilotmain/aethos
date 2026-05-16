# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_event_intelligence import infer_category_severity


def test_failure_severity() -> None:
    _, sev = infer_category_severity("deployment_failed")
    assert sev == "error"

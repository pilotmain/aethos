# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_metrics_discipline import (
    get_runtime_discipline_metrics,
    record_discipline_counter,
)


def test_discipline_counter() -> None:
    record_discipline_counter("test_counter", detail="step11")
    m = get_runtime_discipline_metrics()
    assert isinstance(m, dict)

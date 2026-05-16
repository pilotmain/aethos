# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_metrics_discipline import approx_payload_bytes
from app.services.mission_control.runtime_truth import build_runtime_truth

_OFFICE_MAX_BYTES = 512_000


def test_office_payload_stays_bounded() -> None:
    truth = build_runtime_truth(user_id=None)
    office = truth.get("office") or {}
    size = approx_payload_bytes(office if isinstance(office, dict) else {})
    assert size < _OFFICE_MAX_BYTES, f"office payload {size} exceeds cap"

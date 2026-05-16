# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_identity import build_runtime_identity
from app.services.mission_control.runtime_truth import build_runtime_truth


def test_runtime_identity_flow() -> None:
    truth = build_runtime_truth(user_id=None)
    ident = build_runtime_identity(truth)
    assert ident.get("terminology_version") == "phase3_step15"

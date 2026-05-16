# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.worker_deliverable_ops import apply_deliverable_privacy


def test_deliverable_privacy_metadata_attached() -> None:
    row = apply_deliverable_privacy(
        {
            "summary": "routine output",
            "content": "no secrets here",
        }
    )
    assert "privacy_metadata" in row
    assert "mode" in row["privacy_metadata"]

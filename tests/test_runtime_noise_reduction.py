# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_launch_focus import build_runtime_noise_reduction


def test_runtime_noise_reduction_collapses_chatter() -> None:
    out = build_runtime_noise_reduction({})
    assert out["duplicate_chatter_suppressed"] is True
    assert out["repetitive_warnings_collapsed"] is True

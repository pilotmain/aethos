# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.strategic_differentiation import build_strategic_differentiation_summary


def test_strategic_differentiation_preserves_parity() -> None:
    out = build_strategic_differentiation_summary({})
    assert out.get("openclaw_parity") == "preserved"
    assert "phase4_advantages" in out

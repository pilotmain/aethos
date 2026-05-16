# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.aethos_differentiation import build_differentiators_summary


def test_differentiators_summary_shape() -> None:
    d = build_differentiators_summary()
    assert "advantages" in d
    assert "privacy_posture" in d
    assert "brain_routing" in d
    assert d.get("openclaw_parity") == "maintained"

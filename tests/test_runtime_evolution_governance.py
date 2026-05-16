# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.mission_control.runtime_evolution_governance import (
    build_governance_maturity,
    build_runtime_evolution_governance,
)


def test_runtime_evolution_governance_requires_review() -> None:
    out = build_runtime_evolution_governance({})
    assert out.get("requires_operator_review") is True
    assert out.get("governance_visible") is True


def test_governance_maturity_explainable() -> None:
    out = build_governance_maturity({"governance_readiness": {"score": 0.9}})
    assert out.get("explainable") is True
    assert out.get("maturity_score") == 0.9

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_evolution_memory import build_runtime_evolution_memory


def test_runtime_evolution_memory_bounded() -> None:
    out = build_runtime_evolution_memory({"runtime_readiness_score": 0.8})
    assert out.get("bounded") is True
    assert out.get("searchable") is True

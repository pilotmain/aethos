# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_operational_memory_discipline import build_runtime_operational_memory_discipline


def test_memory_discipline() -> None:
    out = build_runtime_operational_memory_discipline({})
    assert out["operational_memory_discipline"]["bounded"] is True

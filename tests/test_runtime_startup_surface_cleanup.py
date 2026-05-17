# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_operator_surface import (
    build_operator_startup_lines,
    print_advanced_runtime_endpoints,
)


def test_startup_surface_prioritizes_mission_control() -> None:
    lines = build_operator_startup_lines()
    text = "\n".join(lines)
    assert "Mission Control:" in text
    assert "http://localhost:3000" in text
    assert "/dashboard" not in text
    assert "Swagger" not in text
    assert "ReDoc" not in text
    assert "nexa" not in text.lower()


def test_advanced_endpoints_include_swagger_when_requested(capsys) -> None:
    print_advanced_runtime_endpoints()
    out = capsys.readouterr().out
    assert "/docs" in out
    assert "Swagger" in out

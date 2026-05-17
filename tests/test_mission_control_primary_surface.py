# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_operator_surface import build_operator_startup_lines


def test_mission_control_before_api_docs() -> None:
    lines = build_operator_startup_lines()
    text = "\n".join(lines)
    mc = text.index("Mission Control")
    api = text.index("API:")
    assert mc < api
    assert "Status:" in text

# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_health_authority import runtime_health_summary_lines


def test_startup_operational_readiness_visibility() -> None:
    lines = runtime_health_summary_lines()
    text = "\n".join(lines)
    assert "API:" in text
    assert "Runtime ownership:" in text

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.runtime.runtime_progressive_startup import (
    PROGRESSIVE_STARTUP_STAGES,
    build_startup_health_dashboard,
    orchestrate_progressive_startup,
)


def test_progressive_startup_stages_count() -> None:
    assert len(PROGRESSIVE_STARTUP_STAGES) == 7


def test_health_dashboard_offline() -> None:
    lines = build_startup_health_dashboard(api_port=8010, api_reachable=False, mc_reachable=False)
    text = "\n".join(lines)
    assert "API:" in text
    assert "Mission Control:" in text


def test_save_only_skips_start() -> None:
    result = orchestrate_progressive_startup(choice="save_only")
    assert result["started"] is False

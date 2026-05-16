# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.runtime_agents import office_agent_states


def test_office_states_include_orchestrator() -> None:
    rows = office_agent_states()
    assert any(r.get("agent_type") == "orchestrator" for r in rows)

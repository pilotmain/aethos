# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.workspace_runtime_intelligence import build_workspace_operational_summaries


def test_summaries_keys() -> None:
    s = build_workspace_operational_summaries()
    assert "project_summary" in s
    assert "research_summary" in s

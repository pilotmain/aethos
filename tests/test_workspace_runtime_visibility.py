# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.workspace_runtime_intelligence import build_workspace_intelligence


def test_workspace_intelligence_shape() -> None:
    out = build_workspace_intelligence()
    assert "projects" in out
    assert "project_count" in out

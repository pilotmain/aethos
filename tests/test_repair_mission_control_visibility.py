# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.runtime.runtime_state import default_runtime_state, save_runtime_state
from app.services.operator_context import build_operator_context_panel


def test_operator_context_includes_brain_summary(tmp_path) -> None:
    st = default_runtime_state(workspace_root=tmp_path / "ws")
    st["repair_contexts"] = {
        "latest_by_project": {"acme": "r1"},
        "acme": {
            "r1": {
                "repair_context_id": "r1",
                "project_id": "acme",
                "brain_decision": {
                    "selected_provider": "deterministic",
                    "selected_model": "deterministic-repair-v1",
                    "reason": "tests",
                },
                "evidence_summary": {"privacy": {"findings": []}},
            }
        },
    }
    save_runtime_state(st)
    panel = build_operator_context_panel()
    row = (panel.get("latest_repair_contexts") or {}).get("acme") or {}
    assert row.get("brain_summary", {}).get("provider") == "deterministic"

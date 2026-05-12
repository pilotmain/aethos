# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 24 — DevOpsPanel data contract (keys from Mission Control snapshot)."""


def test_dev_run_snapshot_includes_agent_privacy_fields() -> None:
    """Keep aligned with ``build_execution_snapshot`` + ``DevOpsPanel.tsx``."""
    keys = {
        "id",
        "workspace_id",
        "goal",
        "status",
        "created_at",
        "completed_at",
        "error",
        "adapter_used",
        "preferred_agent",
        "privacy_note",
    }
    assert {"adapter_used", "preferred_agent", "privacy_note"}.issubset(keys)

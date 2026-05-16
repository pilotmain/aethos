# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import build_workspace_awareness_snippet


def test_workspace_snippet_shape() -> None:
    sn = build_workspace_awareness_snippet()
    assert "at" in sn

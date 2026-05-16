# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.worker_memory_archive import summarize_worker_memory


def test_worker_memory_summarize() -> None:
    out = summarize_worker_memory({"worker_deliverables": [{"id": i} for i in range(60)]})
    assert out["archived_deliverables"] > 0
    assert out["active_deliverables"] <= 48

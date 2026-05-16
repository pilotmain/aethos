# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_enterprise_summarization import build_enterprise_runtime_summaries


def test_enterprise_summaries() -> None:
    out = build_enterprise_runtime_summaries({"operational_pressure": {"level": "low"}})
    assert out["summary_first"] is True
    assert "operational_summary" in out
    assert "worker_summary" in out

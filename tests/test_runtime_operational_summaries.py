# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.operational_intelligence_engine import build_operational_summaries


def test_summary_keys() -> None:
    from app.services.operational_intelligence import build_operational_intelligence
    from app.runtime.automation_pack_runtime import build_automation_pack_runtime_truth
    from app.services.workspace_runtime_intelligence import build_operational_risk, build_workspace_intelligence

    s = build_operational_summaries(
        build_operational_intelligence(),
        build_automation_pack_runtime_truth(),
        build_workspace_intelligence(),
        build_operational_risk(),
    )
    assert "runtime_operational_summary" in s
    assert "governance_summary" in s

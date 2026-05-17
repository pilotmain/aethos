# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_explainability_finalization import build_runtime_explainability_finalization


def test_explainability_finalization() -> None:
    out = build_runtime_explainability_finalization({"routing_summary": {}})
    assert "domains_covered" in out["runtime_explainability_finalization"]

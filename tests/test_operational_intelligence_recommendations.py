# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.operational_intelligence_recommendations import enrich_recommendations_strategic


def test_enrich_recommendations_strategic() -> None:
    truth = {
        "runtime_recommendations": {
            "recommendations": [{"message": "test", "operational_impact": "medium"}]
        }
    }
    enrich_recommendations_strategic(truth)
    rec = truth["runtime_recommendations"]["recommendations"][0]
    assert rec.get("advisory_only") is True
    assert "strategic_relevance" in rec

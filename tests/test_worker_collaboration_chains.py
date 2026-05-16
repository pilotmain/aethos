# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.runtime_truth import build_runtime_truth
from app.services.mission_control.worker_collaboration_visibility import build_worker_collaboration_chains_enriched


def test_enriched_chain() -> None:
    chains = build_worker_collaboration_chains_enriched({"runtime_recommendations": {"recommendations": []}})
    if chains:
        assert "aethos_orchestrator" in chains[0].get("chain", [])

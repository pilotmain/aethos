# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_readiness_convergence import CANONICAL_READINESS_STATES, build_runtime_readiness_convergence


def test_runtime_readiness_transitions() -> None:
    blob = build_runtime_readiness_convergence({"production_runtime_finalized": True})
    assert blob["runtime_readiness_convergence"]["canonical_state"] in CANONICAL_READINESS_STATES

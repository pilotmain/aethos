# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import (
    OPERATOR_READINESS_STATES,
    derive_operator_readiness_state,
)
from app.services.runtime.runtime_readiness_convergence import CANONICAL_READINESS_STATES


def test_operator_readiness_states_include_spec_values() -> None:
    for state in ("initializing", "warming", "partially_operational", "operational", "degraded", "recovering", "maintenance"):
        assert state in OPERATOR_READINESS_STATES or state in CANONICAL_READINESS_STATES


def test_derive_operator_readiness_partial_when_hydrating() -> None:
    assert derive_operator_readiness_state(api_reachable=True, mc_reachable=True, hydration_partial=True) == "partially_operational"


def test_derive_operator_readiness_operational_when_ready() -> None:
    assert (
        derive_operator_readiness_state(
            api_reachable=True,
            mc_reachable=True,
            db_healthy=True,
            hydration_partial=False,
        )
        == "operational"
    )

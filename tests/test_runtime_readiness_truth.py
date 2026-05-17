# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_readiness_convergence import build_runtime_readiness_convergence


def test_runtime_readiness_truth() -> None:
    blob = build_runtime_readiness_convergence({"runtime_readiness_score": 0.9})
    assert blob["runtime_readiness_convergence"]["single_authority"] is True

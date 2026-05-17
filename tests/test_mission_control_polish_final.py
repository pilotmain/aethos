# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_api_capabilities import MC_COMPATIBILITY_VERSION


def test_mc_compatibility_step21() -> None:
    assert MC_COMPATIBILITY_VERSION == "phase4_step21"

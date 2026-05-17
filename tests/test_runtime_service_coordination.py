# SPDX-License-Identifier: Apache-2.0

from aethos_cli.setup_supervision_preflight import run_setup_supervision_preflight


def test_runtime_service_coordination_preflight_shape() -> None:
    pre = run_setup_supervision_preflight()
    assert "health" in pre
    assert "needs_recovery" in pre
    assert "canonical_ports" in pre

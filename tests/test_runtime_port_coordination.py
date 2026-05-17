# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_port_coordination import get_canonical_runtime_ports, probe_runtime_ports


def test_canonical_ports_include_api_mc_legacy() -> None:
    ports = get_canonical_runtime_ports()
    assert ports["api"] in (8000, 8010)
    assert ports["mission_control"] == 3000
    assert ports["legacy_worker"] == 8000


def test_probe_runtime_ports_shape() -> None:
    probed = probe_runtime_ports()
    assert 3000 in probed
    assert 8000 in probed

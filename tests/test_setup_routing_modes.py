# SPDX-License-Identifier: Apache-2.0

from aethos_cli.setup_routing import CANONICAL_ROUTING_MODES, canonical_routing_label


def test_setup_routing_modes() -> None:
    assert canonical_routing_label("hybrid") == "Hybrid"
    assert "cloud_only" in CANONICAL_ROUTING_MODES
    summary = CANONICAL_ROUTING_MODES["local_only"]["summary"]
    assert "cloud only" not in summary.lower() or "cloud-first" in summary.lower()

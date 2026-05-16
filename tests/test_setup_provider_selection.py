# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_routing import build_routing_env_updates


def test_setup_routing_hybrid() -> None:
    u = build_routing_env_updates("hybrid", preference="balanced")
    assert u["AETHOS_LOCAL_FIRST"] == "true"
    assert u["AETHOS_LOCAL_ONLY"] == "false"

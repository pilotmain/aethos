# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.runtime_strategy_onboarding import (
    build_provider_routing_explained,
    build_runtime_strategy_onboarding,
)


def test_runtime_strategy_onboarding() -> None:
    out = build_runtime_strategy_onboarding("local-first")
    assert out["runtime_strategy_onboarding"]["selected"] == "local-first"
    routing = build_provider_routing_explained()
    assert routing["provider_routing_explained"]["advisory_first"] is True

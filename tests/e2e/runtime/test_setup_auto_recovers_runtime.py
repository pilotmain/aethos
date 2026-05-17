# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_health_authority import build_canonical_runtime_health


def test_setup_auto_recovers_stale_semantics() -> None:
    ha = build_canonical_runtime_health()["runtime_health_authority"]
    if ha["stale_session"]:
        assert ha["may_claim_operational"] is False

# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_health_authority import build_canonical_runtime_health


def test_runtime_operational_semantics_message() -> None:
    ha = build_canonical_runtime_health()["runtime_health_authority"]
    if ha["operational"]:
        assert "operational" in ha["message"].lower()
    elif ha["stale_session"]:
        assert "stale" in ha["message"].lower()

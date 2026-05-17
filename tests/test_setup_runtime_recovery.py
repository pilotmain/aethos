# SPDX-License-Identifier: Apache-2.0

from app.services.setup.setup_operational_recovery import build_setup_operational_recovery


def test_setup_runtime_recovery_repair_scope() -> None:
    blob = build_setup_operational_recovery()
    scope = blob["setup_operational_recovery"]["repair_scope"]
    assert "runtime ownership conflicts" in scope
    assert "stale startup locks" in scope

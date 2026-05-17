# SPDX-License-Identifier: Apache-2.0

from app.services.setup.setup_operational_recovery import build_setup_operational_recovery


def test_setup_operational_recovery() -> None:
    blob = build_setup_operational_recovery()
    assert blob["setup_operational_recovery"]["calm"] is True

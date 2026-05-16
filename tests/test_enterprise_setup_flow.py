# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_status import build_setup_status


def test_setup_status_bounded() -> None:
    out = build_setup_status()
    assert "checks" in out
    assert "setup_modes" in out

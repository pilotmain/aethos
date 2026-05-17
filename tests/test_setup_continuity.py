# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_continuity import build_setup_continuity


def test_setup_continuity() -> None:
    out = build_setup_continuity()
    c = out["setup_continuity"]
    assert "resume" in c["global_commands"]
    assert c["phase"] == "phase4_step19"

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_experience_final import build_setup_experience_final


def test_setup_experience_final() -> None:
    out = build_setup_experience_final()
    assert "help" in out["setup_experience_final"]["global_commands"]

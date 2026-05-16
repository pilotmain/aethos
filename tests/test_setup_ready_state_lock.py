# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_ready_state_lock import build_setup_ready_state_lock


def test_setup_ready_state_lock_bundle() -> None:
    out = build_setup_ready_state_lock()
    assert out["phase"] == "phase4_step15"
    assert "one_curl_certified" in out

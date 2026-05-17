# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority


def test_runtime_ownership_authority_keys() -> None:
    blob = build_runtime_ownership_authority({})
    assert blob["runtime_ownership_authority"]["phase"] == "phase4_step25"
    assert "runtime_process_authority" in blob
    assert "database_runtime_integrity" in blob

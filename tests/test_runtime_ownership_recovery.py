# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_ownership_authority import build_runtime_ownership_authority


def test_runtime_ownership_recovery_authority_shape() -> None:
    blob = build_runtime_ownership_authority({})
    assert "runtime_ownership_authority" in blob

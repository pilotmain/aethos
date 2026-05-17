# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_truth_ownership_lock import build_runtime_truth_authority


def test_runtime_truth_authority_e2e() -> None:
    blob = build_runtime_truth_authority()
    assert "runtime_truth_authoritative" in blob

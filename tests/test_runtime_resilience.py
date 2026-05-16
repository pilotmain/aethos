# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_resilience import (
    build_runtime_resilience_block,
    fetch_slice_resilient,
)


def test_fetch_slice_resilient_unknown_slice() -> None:
    data, status = fetch_slice_resilient("nonexistent_slice_xyz", "u1", fallback={"ok": True})
    assert status in ("degraded", "partial", "stale", "healthy")
    assert data.get("ok") or status != "healthy"


def test_runtime_resilience_block_states() -> None:
    block = build_runtime_resilience_block(status="degraded", failed_endpoints=["office"])
    assert block["status"] == "degraded"
    assert "office" in block["failed_endpoints"]

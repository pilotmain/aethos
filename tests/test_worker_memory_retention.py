# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.core.config import get_settings
from app.runtime.worker_operational_memory import get_worker_memory_limits, persist_deliverable


def test_deliverable_limit_configurable(monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_WORKER_DELIVERABLE_LIMIT", "5")
    get_settings.cache_clear()
    try:
        assert get_worker_memory_limits()["deliverable"] == 5
    finally:
        get_settings.cache_clear()


def test_persist_sets_title() -> None:
    did = persist_deliverable(
        worker_id="ret1",
        task_id="t1",
        deliverable_type="general_output",
        summary="sum",
        content="c",
        title="Custom title",
    )
    from app.runtime.worker_operational_memory import get_deliverable

    row = get_deliverable(did)
    assert row and row.get("title") == "Custom title"

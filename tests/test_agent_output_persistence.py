# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import (
    create_agent_task,
    get_output,
    link_registry_agent_to_runtime,
    record_agent_output,
)


def test_output_persisted() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="o1", name="writer", domain="general")
    aid = str(row["agent_id"])
    tid = create_agent_task(runtime_agent_id=aid, agent_handle="writer", prompt="write report")
    oid = record_agent_output(
        runtime_agent_id=aid,
        task_id=tid,
        summary="done",
        content="Report body here.",
        artifacts=["report.md"],
    )
    out = get_output(oid)
    assert out and "Report body" in out.get("content", "")

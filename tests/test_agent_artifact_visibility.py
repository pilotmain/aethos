# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import (
    create_agent_task,
    link_registry_agent_to_runtime,
    record_agent_output,
)
from app.services.agent_runtime_truth import format_agent_status_reply


def test_artifacts_in_result_reply() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="a1", name="artifact_bot", domain="general")
    aid = str(row["agent_id"])
    tid = create_agent_task(runtime_agent_id=aid, agent_handle="artifact_bot", prompt="export")
    record_agent_output(
        runtime_agent_id=aid,
        task_id=tid,
        summary="exported",
        content="ok",
        artifacts=["out.csv"],
    )
    reply = format_agent_status_reply("artifact_bot")
    assert "Artifacts" in reply or "out.csv" in reply

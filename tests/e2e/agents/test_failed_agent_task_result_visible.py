# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.agent_work_state import (
    create_agent_task,
    link_registry_agent_to_runtime,
    record_agent_output,
)
from app.services.agent_runtime_truth import format_agent_status_reply


def test_failed_task_visible() -> None:
    row = link_registry_agent_to_runtime(registry_agent_id="f1", name="fail_bot", domain="qa")
    aid = str(row["agent_id"])
    tid = create_agent_task(runtime_agent_id=aid, agent_handle="fail_bot", prompt="broken task")
    record_agent_output(
        runtime_agent_id=aid,
        task_id=tid,
        summary="verification failed",
        content="",
        success=False,
    )
    reply = format_agent_status_reply("fail_bot")
    assert "failed" in reply.lower()

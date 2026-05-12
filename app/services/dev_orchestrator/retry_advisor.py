# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations


def advise_retry(job) -> str:
    stage = getattr(job, "failure_stage", None)
    error = ((getattr(job, "error_message", None) or "") + " " + (getattr(job, "result", None) or "")).lower()

    if stage == "dirty_worktree" or "dirty" in error:
        return (
            "Retry is blocked until the repo is clean.\n\n"
            "Run `git status`, then commit, stash, or discard changes."
        )

    if "aider" in error and "not found" in error:
        return (
            "Aider is not available to the worker.\n\n"
            "Check DEV_AGENT_COMMAND and make sure the path exists."
        )

    if "tests failed" in error or stage == "tests":
        return (
            "The change ran but tests failed.\n\n"
            "Inspect test output for that job, then retry or request changes."
        )

    if "timeout" in error:
        return (
            "The job timed out.\n\n"
            "Try a smaller task or switch the project to ide_handoff mode."
        )

    jid = getattr(job, "id", "")
    return (
        "You can retry this job, but review the logs first (ask about job #"
        f"{jid} in chat or use the web app)."
    ).strip()

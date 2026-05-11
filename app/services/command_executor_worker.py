"""Worker helper for executing approved command jobs."""

from __future__ import annotations

from typing import Any

from app.services.host_executor import execute_command


async def process_command_job(job_id: int, command: str, cwd: str | None = None) -> dict[str, Any]:
    """Execute an approved command and normalize the worker result."""
    result = await execute_command(command, cwd)
    return {
        "status": "completed" if result.get("success") else "failed",
        "output": result.get("stdout", ""),
        "error": result.get("stderr") or result.get("error"),
        "job_id": job_id,
    }

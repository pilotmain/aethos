# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path

from app.services.dev_tools.base import DevToolConnector, DevToolResult


class AiderConnector(DevToolConnector):
    key = "aider"
    display_name = "Aider"
    supported_modes = ["autonomous_cli"]

    def is_available(self) -> bool:
        command = os.getenv("DEV_AGENT_COMMAND", "").strip()
        if command:
            first = shlex.split(command)[0]
            return Path(first).exists() or shutil.which(first) is not None
        return shutil.which("aider") is not None

    def open_project(
        self, repo_path: Path, task_file: Path | None = None
    ) -> DevToolResult:
        return DevToolResult(
            ok=True,
            message=f"Aider is CLI-based. Project path: {repo_path}",
        )

    def run_autonomous(self, repo_path: Path, task_file: Path) -> DevToolResult:
        command_template = os.getenv(
            "DEV_AGENT_COMMAND",
            "aider --yes --no-auto-commits --message-file {task_file}",
        )

        command = command_template.replace("{task_file}", str(task_file))

        parts = shlex.split(command, posix=os.name != "nt")
        if not parts:
            return DevToolResult(ok=False, message="Empty DEV_AGENT_COMMAND after parse.")

        result = subprocess.run(  # noqa: S603
            parts,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=int(os.getenv("DEV_AGENT_TIMEOUT_SECONDS", "1800")),
        )

        output = ((result.stdout or "") + "\n" + (result.stderr or ""))[-5000:]

        return DevToolResult(
            ok=result.returncode == 0,
            message="Aider completed." if result.returncode == 0 else "Aider failed.",
            details=output,
        )

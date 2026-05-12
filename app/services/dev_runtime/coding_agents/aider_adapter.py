# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Aider CLI adapter — local subprocess, dry-run unless write is allowed."""

from __future__ import annotations

import shutil
import subprocess

from app.core.config import get_settings
from app.services.dev_runtime.coding_agents.base import (
    CodingAgentAdapter,
    CodingAgentRequest,
    CodingAgentResult,
)
from app.services.dev_runtime.privacy import redact_output_for_storage


def _tail(s: str | None, n: int = 4000) -> str:
    t = s or ""
    return t[-n:] if len(t) > n else t


class AiderCodingAgent(CodingAgentAdapter):
    name = "aider"

    def available(self) -> bool:
        s = get_settings()
        if not s.nexa_aider_enabled:
            return False
        cmd = (s.nexa_aider_command or "aider").strip()
        return bool(shutil.which(cmd))

    def run(self, request: CodingAgentRequest) -> CodingAgentResult:
        s = get_settings()
        exe = (s.nexa_aider_command or "aider").strip() or "aider"
        cmd: list[str] = [
            exe,
            "--message",
            (request.goal or "").strip()[:50_000],
        ]
        if request.allow_write:
            cmd.append("--yes-always")
        else:
            cmd.append("--dry-run")

        timeout = max(5, int(s.nexa_dev_command_timeout_seconds or 180))
        try:
            proc = subprocess.run(
                cmd,
                cwd=request.repo_path,
                capture_output=True,
                text=True,
                timeout=float(timeout),
            )
        except subprocess.TimeoutExpired:
            return CodingAgentResult(
                ok=False,
                provider="aider",
                summary="",
                changed_files=[],
                commands_run=[" ".join(cmd)],
                error="aider_timeout",
            )
        except OSError as exc:
            return CodingAgentResult(
                ok=False,
                provider="aider",
                summary="",
                changed_files=[],
                commands_run=[" ".join(cmd)],
                error=str(exc)[:4000],
            )

        out = redact_output_for_storage(_tail(proc.stdout))
        err = redact_output_for_storage(_tail(proc.stderr)) if proc.returncode != 0 else None
        return CodingAgentResult(
            ok=proc.returncode == 0,
            provider="aider",
            summary=out,
            changed_files=[],
            commands_run=[" ".join(cmd)],
            test_result={"returncode": proc.returncode},
            error=err,
        )


__all__ = ["AiderCodingAgent"]

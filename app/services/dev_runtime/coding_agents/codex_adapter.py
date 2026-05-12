# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenAI Codex CLI adapter — feature-flagged local wrapper."""

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


class CodexCodingAgent(CodingAgentAdapter):
    name = "codex"

    def available(self) -> bool:
        s = get_settings()
        if not s.nexa_codex_enabled:
            return False
        cmd = (s.nexa_codex_command or "codex").strip()
        return bool(shutil.which(cmd))

    def run(self, request: CodingAgentRequest) -> CodingAgentResult:
        _ = (request.goal or "")[:1]
        if not self.available():
            return CodingAgentResult(
                ok=False,
                provider="codex",
                summary="",
                changed_files=[],
                commands_run=[],
                error="codex_disabled_or_binary_missing",
            )
        s = get_settings()
        exe = (s.nexa_codex_command or "codex").strip()
        cmd = [exe, "--help"]
        timeout = min(60, max(5, int(s.nexa_dev_command_timeout_seconds or 180)))
        try:
            proc = subprocess.run(
                cmd,
                cwd=request.repo_path,
                capture_output=True,
                text=True,
                timeout=float(timeout),
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            return CodingAgentResult(
                ok=False,
                provider="codex",
                summary="",
                changed_files=[],
                commands_run=[" ".join(cmd)],
                error=str(exc)[:4000],
            )
        out = redact_output_for_storage((proc.stdout or "")[-4000:])
        err = (
            redact_output_for_storage((proc.stderr or "")[-4000:])
            if proc.returncode != 0
            else None
        )
        return CodingAgentResult(
            ok=proc.returncode == 0,
            provider="codex",
            summary=out or "(no stdout)",
            changed_files=[],
            commands_run=[" ".join(cmd)],
            error=err,
        )


__all__ = ["CodexCodingAgent"]

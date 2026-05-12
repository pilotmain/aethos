# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Run resolved CLI argv via :func:`~app.services.cli_backends.get_cli_command`.

One-shot ``subprocess`` / asyncio helpers. **Persistent stdio sessions** (long-lived codex/claude-style
processes) are not implemented; backends with ``persistent_session=True`` log a warning and use a
single subprocess invocation.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Optional

from app.services.cli_backends import get_cli_backend, get_cli_command

logger = logging.getLogger("nexa.cli_executor")


def _warn_if_persistent_requested(cli_name: str) -> None:
    b = get_cli_backend(cli_name)
    if b and b.persistent_session:
        logger.warning(
            "nexa.cli_executor: persistent_session for %r is not implemented; using one-shot subprocess",
            cli_name,
        )


def run_cli_subprocess(
    cli_name: str,
    args: list[str],
    *,
    cwd: Optional[str] = None,
    timeout: Optional[float] = None,
    env: Optional[dict[str, str]] = None,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Sync ``subprocess.run`` with CLI backend resolution."""
    _warn_if_persistent_requested(cli_name)
    cmd = get_cli_command(cli_name, args)
    return subprocess.run(  # noqa: S603 — argv from allowlisted resolution only
        cmd,
        cwd=cwd,
        timeout=timeout,
        env=env,
        capture_output=capture_output,
        text=text,
    )


async def run_cli_async(
    cli_name: str,
    args: list[str],
    *,
    cwd: Optional[str] = None,
    timeout: Optional[float] = None,
    env: Optional[dict[str, str]] = None,
    input_text: Optional[str] = None,
) -> subprocess.CompletedProcess[str | bytes]:
    """Async subprocess with CLI backend resolution."""
    _warn_if_persistent_requested(cli_name)
    cmd = get_cli_command(cli_name, args)
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=cwd,
        env=env,
        stdin=asyncio.subprocess.PIPE if input_text is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    in_bytes = input_text.encode() if input_text is not None else None
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(in_bytes), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    code = proc.returncode if proc.returncode is not None else -1
    return subprocess.CompletedProcess(
        args=cmd,
        returncode=code,
        stdout=stdout or b"",
        stderr=stderr or b"",
    )


async def cleanup_cli_sessions() -> None:
    """Reserved for future persistent sessions; no-op today."""
    return None


__all__ = [
    "cleanup_cli_sessions",
    "run_cli_async",
    "run_cli_subprocess",
]

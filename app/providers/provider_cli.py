# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import subprocess
from pathlib import Path


def run_cli_argv(
    argv: list[str],
    *,
    timeout_sec: float,
    cwd: Path | None = None,
) -> tuple[int, str, str]:
    """Run a CLI argv list (no shell). Returns ``(returncode, stdout, stderr)``."""
    if not argv:
        return 1, "", ""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout_sec)),
            cwd=str(cwd) if cwd else None,
            check=False,
        )
        return int(proc.returncode or 0), proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", "cli_timeout"
    except OSError as exc:
        return 1, "", str(exc)

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Allowlisted one-shot shell helpers (no arbitrary user shell)."""

from __future__ import annotations

import subprocess
from typing import Any


def run_allowlisted_shell(
    argv: list[str],
    *,
    allowlist: frozenset[tuple[str, ...]],
    cwd: str | None = None,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    """
    Run ``argv`` only if the exact tuple is in ``allowlist``.

    Returns stdout/stderr snippets (bounded); never raises for tool UX — ``ok`` flag.
    """
    tup = tuple(argv)
    if tup not in allowlist:
        return {"ok": False, "error": "not_allowlisted", "argv": list(argv)}
    try:
        proc = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout_sec,
            check=False,
        )
        out = (proc.stdout or "")[:8000]
        err = (proc.stderr or "")[:4000]
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": out,
            "stderr": err,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "argv": list(argv)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "argv": list(argv)}


__all__ = ["run_allowlisted_shell"]

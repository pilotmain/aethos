# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""OpenClaw-class CLI helpers: ``doctor`` (sanity) and ``logs`` (local tail)."""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _tail_file(path: Path, *, max_lines: int) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    if len(raw) <= max_lines:
        return raw
    return raw[-max_lines:]


def cmd_logs(*, lines: int = 80) -> int:
    """Print recent lines from ``~/.aethos/logs/*.log`` or repo ``.runtime/*.log``."""
    roots: list[Path] = []
    home_logs = Path.home() / ".aethos" / "logs"
    home_logs.mkdir(parents=True, exist_ok=True)
    roots.append(home_logs)
    rt = _repo_root() / ".runtime"
    if rt.is_dir():
        roots.append(rt)

    candidates: list[Path] = []
    for d in roots:
        if not d.is_dir():
            continue
        for p in d.glob("*.log"):
            if p.is_file():
                candidates.append(p)
    if not candidates:
        print(
            "No ``*.log`` files found under ~/.aethos/logs or <repo>/.runtime yet.\n"
            "Start the gateway (``aethos gateway`` / ``aethos serve``) and retry.",
            file=sys.stderr,
        )
        return 0

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"--- {newest} (last {lines} lines) ---", file=sys.stderr)
    for ln in _tail_file(newest, max_lines=max(1, int(lines))):
        print(ln)
    return 0


def cmd_doctor(*, api_base: str) -> int:
    """Compile check + optional ``GET /api/v1/health``."""
    root = _repo_root()
    print("== AethOS doctor (OpenClaw-class diagnostics) ==", file=sys.stderr)
    r = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", "app"],
        cwd=str(root),
        check=False,
    )
    if r.returncode != 0:
        print("compileall: FAIL", file=sys.stderr)
        return 1
    print("compileall: OK", file=sys.stderr)

    base = (api_base or "").strip().rstrip("/")
    url = f"{base}/api/v1/health"
    try:
        req = urllib.request.Request(url, method="GET", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            code = resp.getcode()
            body = resp.read()[:4000].decode(errors="replace")
        print(f"health HTTP {code}: {body[:500]}", file=sys.stderr)
    except urllib.error.HTTPError as e:
        print(f"health HTTP {e.code} (API may be down or auth required)", file=sys.stderr)
        return 0
    except OSError as e:
        print(f"health: skip ({e})", file=sys.stderr)
    return 0

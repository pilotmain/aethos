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


def _home_log_roots() -> list[Path]:
    from app.core.paths import get_aethos_home_dir

    h = get_aethos_home_dir() / "logs"
    h.mkdir(parents=True, exist_ok=True)
    roots = [h]
    rt = _repo_root() / ".runtime"
    if rt.is_dir():
        roots.append(rt)
    return roots


def _log_name_matches_category(name: str, category: str | None) -> bool:
    n = name.lower()
    if not category:
        return True
    if category == "gateway":
        return any(x in n for x in ("gateway", "uvicorn", "aethos", "api"))
    if category == "agents":
        return "agent" in n
    if category == "deployments":
        return "deploy" in n
    if category == "runtime":
        return any(x in n for x in ("runtime", "heartbeat", "recovery"))
    return True


def cmd_logs(*, lines: int = 80, category: str | None = None) -> int:
    """Print recent lines from ``~/.aethos/logs/*.log`` or ``<repo>/.runtime/*.log``."""
    if category == "runtime":
        from app.core.paths import get_runtime_state_path

        p = get_runtime_state_path()
        if p.is_file():
            print(f"--- {p} (last {lines} lines) ---", file=sys.stderr)
            for ln in _tail_file(p, max_lines=max(1, int(lines))):
                print(ln)
            return 0
        print("No ~/.aethos/aethos.json yet — start ``aethos gateway`` once.", file=sys.stderr)
        return 0

    candidates: list[Path] = []
    for d in _home_log_roots():
        if not d.is_dir():
            continue
        for p in d.glob("*.log"):
            if p.is_file() and _log_name_matches_category(p.name, category):
                candidates.append(p)
    if not candidates:
        print(
            "No matching ``*.log`` files.\n"
            "Try: ``aethos logs`` (all) or ``aethos logs gateway|agents|deployments|runtime``.",
            file=sys.stderr,
        )
        return 0

    newest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"--- {newest} (last {lines} lines) ---", file=sys.stderr)
    for ln in _tail_file(newest, max_lines=max(1, int(lines))):
        print(ln)
    return 0


def _runtime_doctor_messages() -> list[str]:
    out: list[str] = []
    try:
        from app.runtime.runtime_workspace import ensure_runtime_workspace_layout

        ensure_runtime_workspace_layout()
        out.append("runtime_workspace: OK")
    except Exception as exc:
        out.append(f"runtime_workspace: FAIL ({exc})")
        return out
    try:
        from app.core.paths import get_runtime_state_path, get_aethos_workspace_root
        from app.runtime.runtime_recovery import reconcile_stale_gateway_pid
        from app.runtime.runtime_state import load_runtime_state, save_runtime_state

        ws = get_aethos_workspace_root()
        out.append(f"workspace_root exists={ws.is_dir()} path={ws}")
        p = get_runtime_state_path()
        if not p.is_file():
            out.append("aethos.json: absent (created on next API boot)")
            return out
        st = load_runtime_state()
        reconcile_stale_gateway_pid(st)
        save_runtime_state(st)
        out.append("aethos.json: OK (reconciled stale gateway pid if any)")
    except Exception as exc:
        out.append(f"runtime_state: FAIL ({exc})")
    return out


def cmd_doctor(*, api_base: str) -> int:
    """Compile check + optional ``GET /api/v1/health`` + runtime parity checks."""
    root = _repo_root()
    print("== AethOS doctor (OpenClaw-class diagnostics) ==", file=sys.stderr)
    for label, rel in (("app", "app"), ("aethos_cli", "aethos_cli")):
        r = subprocess.run(
            [sys.executable, "-m", "compileall", "-q", rel],
            cwd=str(root),
            check=False,
        )
        if r.returncode != 0:
            print(f"compileall {label}: FAIL", file=sys.stderr)
            return 1
        print(f"compileall {label}: OK", file=sys.stderr)

    for ln in _runtime_doctor_messages():
        print(ln, file=sys.stderr)

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

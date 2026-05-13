# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CLI helpers for soul versioning (HTTP API + local snapshot files under ``~/.aethos/soul_history/``)."""

from __future__ import annotations

import difflib
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Callable


def _base_url() -> str:
    return (
        os.environ.get("AETHOS_API_BASE")
        or os.environ.get("NEXA_API_BASE")
        or os.environ.get("API_BASE_URL")
        or "http://127.0.0.1:8010"
    ).rstrip("/")


def _headers(uid: str) -> dict[str, str]:
    h = {"X-User-Id": uid, "Accept": "application/json"}
    tok = (
        os.environ.get("AETHOS_WEB_API_TOKEN") or os.environ.get("NEXA_WEB_API_TOKEN") or ""
    ).strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _req(
    method: str,
    path: str,
    *,
    uid: str,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str]:
    url = f"{_base_url()}{path}"
    h = _headers(uid)
    if content_type:
        h["Content-Type"] = content_type
    elif body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.getcode(), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def cmd_soul_history(uid: str) -> int:
    from app.services.soul_manager import get_user_soul_history

    versions = get_user_soul_history(uid)
    if not versions:
        print("No soul history found for this user id (snapshots appear after soul text changes).")
        return 0
    print("Soul versions (newest first):")
    for v in versions:
        print(f"  {v}")
    return 0


def cmd_soul_diff(uid: str, version: str) -> int:
    from app.services.soul_manager import read_user_soul_version

    old = read_user_soul_version(uid, version)
    if old is None:
        print(f"Version {version!r} not found.", file=sys.stderr)
        return 1
    code, body = _req("GET", "/api/v1/web/memory/state", uid=uid)
    if code != 200:
        print(body, file=sys.stderr)
        return 1
    cur = str((json.loads(body) or {}).get("soul_markdown") or "")
    a = old.splitlines(keepends=True)
    b = cur.splitlines(keepends=True)
    diff = difflib.unified_diff(a, b, fromfile=f"soul@{version}", tofile="soul@current", lineterm="")
    sys.stdout.writelines(diff)
    return 0


def cmd_soul_rollback(uid: str, version: str) -> int:
    from app.services.soul_manager import read_user_soul_version

    blob = read_user_soul_version(uid, version)
    if blob is None:
        print(f"Version {version!r} not found.", file=sys.stderr)
        return 1
    payload = json.dumps({"content": blob}).encode()
    code, body = _req("PUT", "/api/v1/web/memory/soul", uid=uid, body=payload)
    print(body[:8000] if code == 200 else body, file=sys.stderr if code != 200 else sys.stdout)
    return 0 if code == 200 else 1


def cmd_soul_add(uid: str, rule: str) -> int:
    text = (rule or "").strip()
    if not text:
        print("Empty rule.", file=sys.stderr)
        return 1
    code0, b0 = _req("GET", "/api/v1/web/memory/state", uid=uid)
    if code0 != 200:
        print(b0, file=sys.stderr)
        return 1
    cur = str((json.loads(b0) or {}).get("soul_markdown") or "").rstrip()
    line = text if text.startswith(("-", "*", "1.")) else f"- {text}"
    merged = (cur + "\n" + line + "\n") if cur else f"# Soul\n\n{line}\n"
    payload = json.dumps({"content": merged}).encode()
    code1, b1 = _req("PUT", "/api/v1/web/memory/soul", uid=uid, body=payload)
    print(b1[:8000] if code1 == 200 else b1, file=sys.stderr if code1 != 200 else sys.stdout)
    return 0 if code1 == 200 else 1


def soul_dispatch(
    soul_cmd: str,
    uid: str,
    argv: list[str],
    *,
    req: Callable[..., tuple[int, str]] | None = None,
) -> int:
    """Entry used from ``aethos_cli.__main__`` (``req`` reserved for tests)."""
    del req
    if soul_cmd == "history":
        return cmd_soul_history(uid)
    if soul_cmd == "diff":
        if len(argv) < 1:
            print("Usage: aethos soul diff <YYYY-MM-DD_HH-MM-SS_microseconds>", file=sys.stderr)
            return 2
        return cmd_soul_diff(uid, argv[0])
    if soul_cmd == "rollback":
        if len(argv) < 1:
            print("Usage: aethos soul rollback <YYYY-MM-DD_HH-MM-SS_microseconds>", file=sys.stderr)
            return 2
        return cmd_soul_rollback(uid, argv[0])
    if soul_cmd == "add":
        if not argv:
            print('Usage: aethos soul add "…"', file=sys.stderr)
            return 2
        return cmd_soul_add(uid, " ".join(argv))
    print(f"Unknown soul subcommand: {soul_cmd}", file=sys.stderr)
    return 2


__all__ = ["soul_dispatch"]

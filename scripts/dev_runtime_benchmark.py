#!/usr/bin/env python3
"""Phase 33 — lightweight latency probe against a running API (optional).

Environment:
  NEXA_API_BASE   — default http://127.0.0.1:8010
  NEXA_API_PREFIX — default /api/v1
  NEXA_BENCH_USER — default bench-local-user (sent as X-User-Id)

Skips gracefully when the server is down (exit 0).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any


def _get(url: str, headers: dict[str, str] | None = None, *, timeout: float = 12.0) -> tuple[int, float, bytes]:
    req = urllib.request.Request(url, headers=headers or {})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            dt = time.perf_counter() - t0
            return resp.status, dt, body
    except urllib.error.HTTPError as e:
        dt = time.perf_counter() - t0
        return e.code, dt, (e.read() or b"")


def main() -> int:
    base = (os.environ.get("NEXA_API_BASE") or "http://127.0.0.1:8010").rstrip("/")
    prefix = (os.environ.get("NEXA_API_PREFIX") or "/api/v1").rstrip("/") or "/api/v1"
    uid = (os.environ.get("NEXA_BENCH_USER") or "bench-local-user").strip()
    hdr = {"X-User-Id": uid}

    rows: list[tuple[str, float, int]] = []

    st, dt, _ = _get(f"{base}{prefix}/health")
    rows.append(("GET health", dt, st))

    st2, dt2, raw = _get(f"{base}{prefix}/mission-control/state?hours=1", hdr)
    rows.append(("GET mission-control/state", dt2, st2))
    try:
        parsed: Any = json.loads(raw.decode("utf-8", errors="replace"))
        mc_ok = isinstance(parsed, dict)
    except json.JSONDecodeError:
        mc_ok = False
    if not mc_ok and st2 == 200:
        print("warning: mission-control/state JSON unexpected", file=sys.stderr)

    print(f"base={base} prefix={prefix} user={uid}")
    for label, elapsed, code in rows:
        print(f"  {label}: {elapsed * 1000:.1f} ms  HTTP {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

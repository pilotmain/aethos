#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Smoke check: API health, web system status, public URL script, optional doctor.
Run from repo root: python scripts/verify_nexa_web_stack.py [--api-base URL]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any


def _get(url: str, *, token: str | None, timeout: float = 8.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-User-Id", os.environ.get("VERIFY_NEXA_USER_ID", "web_smoke1"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec: URL from arg/env
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", errors="replace")
    except OSError as e:
        return -1, f"{type(e).__name__}: {e!s}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--api-base",
        default=os.environ.get("NEXA_API_BASE", "http://127.0.0.1:8000"),
        help="API base (no trailing slash), default NEXA_API_BASE or http://127.0.0.1:8000",
    )
    p.add_argument(
        "--token",
        default=os.environ.get("NEXA_WEB_API_TOKEN", ""),
        help="Bearer for /web/* if required (NEXA_WEB_API_TOKEN)",
    )
    p.add_argument("--skip-doctor", action="store_true", help="Skip GET /web/system/doctor (needs auth).")
    args = p.parse_args()
    base = (args.api_base or "").rstrip("/")
    prefix = "/api/v1"
    err: list[str] = []
    st, body = _get(f"{base}{prefix}/health", token=None)
    if st != 200:
        err.append(f"health: HTTP {st} {body[:200]}")
    else:
        print("health: ok")

    st, body = _get(f"{base}{prefix}/web/system/status", token=(args.token or None))
    if st not in (200, 401):
        err.append(f"web/system/status: HTTP {st}")
    elif st == 401:
        print("web/system/status: skipped (401 — set NEXA_WEB_API_TOKEN to verify as authenticated user)")
    else:
        try:
            data: dict[str, Any] = json.loads(body)
            inds = data.get("indicators") or []
            labels = {str((x or {}).get("id")) for x in inds if isinstance(x, dict)}
            for need in ("public_web", "browser_preview", "web_search"):
                if need not in labels:
                    err.append(f"web/system/status: missing indicator id {need!r}")
            if not err:
                print("web/system/status: ok (web access indicators present)")
        except json.JSONDecodeError as e:
            err.append(f"web/system/status: bad JSON: {e}")

    script = os.path.join(os.path.dirname(__file__), "verify_public_web_access.py")
    if os.path.isfile(script):
        r = subprocess.run(  # noqa: S603
            [sys.executable, script, "https://example.com"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            err.append("verify_public_web_access.py: failed (see stderr)")
        else:
            if "200" in r.stdout or "FETCH" in r.stdout or "excerpt" in r.stdout.lower():
                print("verify_public_web_access: ok")
            else:
                err.append("verify_public_web_access: unexpected output")
    else:
        err.append("verify_public_web_access.py not found")

    if not args.skip_doctor and (args.token or ""):
        st, body = _get(f"{base}{prefix}/web/system/doctor", token=str(args.token))
        if st != 200 or '"text"' not in body:
            err.append(f"web/system/doctor: HTTP {st}")
        else:
            print("web/system/doctor: ok")
    elif not args.skip_doctor:
        print("web/system/doctor: skipped (no --token)")

    if err:
        print("Nexa web stack: FAILED", file=sys.stderr)
        for e in err:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("Nexa web stack OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

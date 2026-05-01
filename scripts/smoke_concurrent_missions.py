#!/usr/bin/env python3
"""
Optional load smoke (Phase 11): run many gateway missions concurrently.

Uses the same DB as configured in `.env`. Default concurrency from env
``NEXA_SMOKE_CONCURRENT`` (default 20). Mission text matches parser expectations.

From repo root with venv:

    .venv/bin/python scripts/smoke_concurrent_missions.py
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

MISSION_TEXT = """Researcher: list three short facts about Python asyncio.
Analyst: summarize in one sentence."""


def _one(idx: int) -> tuple[int, str]:
    from app.services.gateway.runtime import NexaGateway

    out = NexaGateway().handle_message(MISSION_TEXT, f"smoke_user_{idx}")
    status = str(out.get("status") or "")
    return idx, status


def main() -> int:
    n = max(1, min(100, int(os.environ.get("NEXA_SMOKE_CONCURRENT", "20"))))
    workers = min(n, 50)
    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_one, i) for i in range(n)]
        for f in as_completed(futures):
            try:
                _i, status = f.result()
                if status in ("completed", "timeout"):
                    ok += 1
            except Exception as exc:
                print("worker failed:", exc, flush=True)
    print(f"smoke_concurrent_missions: finished_ok={ok}/{n}", flush=True)
    return 0 if ok == n else 1


if __name__ == "__main__":
    raise SystemExit(main())

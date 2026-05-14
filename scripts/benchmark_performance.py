#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Measure intent-classification latency (p50 / p95) and coarse RSS samples.

Uses :func:`app.services.intent_classifier.classify_intent_llm` (same JSON path as
production when ``USE_REAL_LLM`` and ``providers_available()`` are true).

Ollama loads weights in the **ollama** server process; this script reports:
  - Python process RSS (current interpreter)
  - Best-effort RSS for a process named ``ollama`` (``ps``), when available

Examples::

    python scripts/benchmark_performance.py --runs 100
    python scripts/benchmark_performance.py --runs 50 --json-out data/benchmark_performance/latest.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

# Repo root = parents[1] from scripts/benchmark_performance.py
_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

os.chdir(_REPO)


def _rss_bytes_current_process() -> int | None:
    """Resident set size for this process (bytes), best-effort."""
    pid = os.getpid()
    try:
        with open(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    parts = line.split()
                    return int(parts[1]) * 1024  # kB → bytes
    except OSError:
        pass
    try:
        out = subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(pid)],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
        if out:
            return int(out) * 1024  # rss column is KiB on macOS / typical ps
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        pass
    return None


def _rss_bytes_ollama_process() -> int | None:
    """Sum RSS for processes whose command line contains ``ollama`` (bytes)."""
    try:
        out = subprocess.check_output(
            ["ps", "-ax", "-o", "pid=,rss=,command="],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    total_kb = 0
    found = False
    for line in out.splitlines():
        line = line.strip()
        if not line or "ollama" not in line.lower():
            continue
        # skip this benchmark script if it ever matched
        if "benchmark_performance" in line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 2:
            continue
        try:
            total_kb += int(parts[1])
            found = True
        except ValueError:
            continue
    return total_kb * 1024 if found else None


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    xs = sorted(sorted_vals)
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] + (xs[hi] - xs[lo]) * frac


def main() -> int:
    parser = argparse.ArgumentParser(description="Intent latency + RSS snapshot for release NFRs.")
    parser.add_argument("--runs", type=int, default=100, help="Timed classify_intent_llm iterations (after warm-up).")
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write JSON metrics (default: data/benchmark_performance/latest.json if dir exists or created).",
    )
    parser.add_argument(
        "--message",
        default="postmortem this outage summary",
        help="User message for each classification call (default exercises analysis intent).",
    )
    args = parser.parse_args()
    if args.runs < 10:
        print("--runs must be >= 10", file=sys.stderr)
        return 2

    from app.core.config import get_settings
    from app.services.intent_classifier import classify_intent_llm
    from app.services.llm.bootstrap import clear_ollama_readiness_cache, is_ollama_ready, register_llm_providers_from_settings
    from app.services.llm.completion import providers_available
    from app.services.llm_key_resolution import get_merged_api_keys

    clear_ollama_readiness_cache()
    register_llm_providers_from_settings()
    s = get_settings()
    m = get_merged_api_keys()
    if not s.use_real_llm:
        print("USE_REAL_LLM is false — enable LLM in .env for meaningful latency.", file=sys.stderr)
        return 2
    if not m.has_any_key and not providers_available():
        print(
            "No LLM providers available (no merged Anthropic/OpenAI keys and providers_available() is false). "
            "Enable Ollama (NEXA_OLLAMA_ENABLED / NEXA_LOCAL_FIRST + running server with models).",
            file=sys.stderr,
        )
        return 2

    msg = (args.message or "").strip() or "postmortem this outage summary"

    rss_py_before = _rss_bytes_current_process()
    rss_ollama_before = _rss_bytes_ollama_process()

    t0 = time.perf_counter()
    classify_intent_llm(msg)
    warm_ms = (time.perf_counter() - t0) * 1000.0

    rss_py_after_warm = _rss_bytes_current_process()
    rss_ollama_after_warm = _rss_bytes_ollama_process()

    latencies: list[float] = []
    for _ in range(args.runs):
        t1 = time.perf_counter()
        classify_intent_llm(msg)
        latencies.append((time.perf_counter() - t1) * 1000.0)

    rss_py_after_batch = _rss_bytes_current_process()
    rss_ollama_after_batch = _rss_bytes_ollama_process()

    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)
    mean = sum(latencies) / len(latencies)

    def _mb(b: int | None) -> float | None:
        if b is None:
            return None
        return round(b / (1024 * 1024), 2)

    payload: dict[str, Any] = {
        "benchmark": "intent_classify_intent_llm_round_trip",
        "user_message": msg,
        "runs": args.runs,
        "warmup_latency_ms": round(warm_ms, 2),
        "latency_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "mean": round(mean, 2),
            "min": round(min(latencies), 2),
            "max": round(max(latencies), 2),
        },
        "rss_mb": {
            "python_before": _mb(rss_py_before),
            "python_after_warmup": _mb(rss_py_after_warm),
            "python_after_batch": _mb(rss_py_after_batch),
            "ollama_before": _mb(rss_ollama_before),
            "ollama_after_warmup": _mb(rss_ollama_after_warm),
            "ollama_after_batch": _mb(rss_ollama_after_batch),
        },
        "settings_snapshot": {
            "nexa_llm_provider": (s.nexa_llm_provider or "").strip(),
            "nexa_ollama_default_model": (s.nexa_ollama_default_model or "").strip(),
            "nexa_ollama_enabled": bool(s.nexa_ollama_enabled),
            "nexa_local_first": bool(getattr(s, "nexa_local_first", False)),
            "merged_has_any_cloud_key": bool(m.has_any_key),
        },
    }

    out_path = args.json_out
    if out_path is None:
        out_dir = _REPO / "data" / "benchmark_performance"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "latest.json"
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("=== AethOS intent performance (classify_intent_llm) ===")
    print(f"Message: {msg!r}")
    print(f"Runs (after warm-up): {args.runs}")
    print(f"Warm-up latency: {warm_ms:.1f} ms")
    print(f"Latency ms — p50: {p50:.1f}  p95: {p95:.1f}  mean: {mean:.1f}  min: {min(latencies):.1f}  max: {max(latencies):.1f}")
    print("RSS MiB (best-effort):")
    print(f"  python before: {payload['rss_mb']['python_before']}")
    print(f"  python after warm-up: {payload['rss_mb']['python_after_warmup']}")
    print(f"  python after batch: {payload['rss_mb']['python_after_batch']}")
    print(f"  ollama* before: {payload['rss_mb']['ollama_before']}")
    print(f"  ollama* after warm-up: {payload['rss_mb']['ollama_after_warmup']}")
    print(f"  ollama* after batch: {payload['rss_mb']['ollama_after_batch']}")
    print(f"Wrote JSON: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

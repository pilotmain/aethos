# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Release gate: critical benchmark + gateway smoke (optional Ollama benchmark).

Environment variables:
  SKIP_RELEASE_GATE_BENCHMARK=1  — skip Ollama intent benchmark (65 cases; slow).
  RELEASE_GATE_OLLAMA_MODEL    — override model tag (default: qwen2.5:7b).
  RELEASE_GATE_BENCH_TIMEOUT   — per-request timeout seconds (default: 300).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]


def test_release_gate_intent_benchmark_ollama() -> None:
    if os.environ.get("SKIP_RELEASE_GATE_BENCHMARK", "").strip().lower() in ("1", "true", "yes"):
        pytest.skip("SKIP_RELEASE_GATE_BENCHMARK set")

    bench = _REPO / "tests" / "benchmark" / "run_benchmark.py"
    assert bench.is_file(), f"missing {bench}"
    model = (os.environ.get("RELEASE_GATE_OLLAMA_MODEL") or "qwen2.5:7b").strip()
    timeout = (os.environ.get("RELEASE_GATE_BENCH_TIMEOUT") or "300").strip()
    proc = subprocess.run(
        [sys.executable, str(bench), "--model", model, "--timeout", timeout],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if proc.returncode != 0:
        tail = (proc.stdout or "")[-4000:] + "\n" + (proc.stderr or "")[-4000:]
        pytest.fail(f"Intent benchmark failed (exit {proc.returncode}):\n{tail}")


def test_release_gate_gateway_file_write() -> None:
    """Host-executor file-write path through gateway (in-process pytest)."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_gateway_host_executor_file_write.py::test_gateway_file_write_phrase_queues_host_executor",
            "-q",
            "--tb=short",
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        pytest.fail(f"Gateway file-write gate failed:\n{proc.stdout}\n{proc.stderr}")


def test_release_gate_telegram_gateway_wiring() -> None:
    """Static / unit-level check that Telegram funnels through gateway (no bot token)."""
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_telegram_routed_to_gateway.py::test_telegram_bot_uses_structured_gateway",
            "-q",
            "--tb=short",
        ],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(f"Telegram gateway wiring gate failed:\n{proc.stdout}\n{proc.stderr}")

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Validate benchmark harness assets (no live Ollama required)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_BENCH_DIR = Path(__file__).resolve().parent / "benchmark"
_PROMPTS = _BENCH_DIR / "prompts.json"


def _load_run_benchmark_module():
    import sys

    path = _BENCH_DIR / "run_benchmark.py"
    name = "run_benchmark_harness"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_prompts_json_schema_and_count() -> None:
    assert _PROMPTS.is_file(), "missing tests/benchmark/prompts.json"
    data = json.loads(_PROMPTS.read_text(encoding="utf-8"))
    assert data.get("benchmark_version") == 1
    cases = data.get("cases")
    assert isinstance(cases, list) and len(cases) >= 50
    intents = data.get("intents")
    assert isinstance(intents, list) and len(intents) >= 10
    for c in cases:
        assert isinstance(c, dict)
        assert c.get("id")
        assert c.get("user") is not None
        exp = c.get("expected")
        assert isinstance(exp, dict) and exp.get("intent")
        assert str(exp["intent"]) in intents, f"intent not in list: {exp['intent']}"


@pytest.mark.parametrize(
    "raw,expected_intent",
    [
        ('{"intent": "greeting", "confidence": 1, "reason": "x"}', "greeting"),
        ('```json\n{"intent": "brain_dump"}\n```', "brain_dump"),
        ('Here: {"intent": "stuck_dev"} thanks', "stuck_dev"),
        (
            '{"intent": "correction", "confidence": 0.9, "reason": "x"}\n\nExtra prose after JSON.',
            "correction",
        ),
    ],
)
def test_extract_json_object(raw: str, expected_intent: str) -> None:
    mod = _load_run_benchmark_module()
    parsed = mod.extract_json_object(raw)
    assert parsed is not None
    assert str(parsed.get("intent") or "").lower() == expected_intent

#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Agent-task intent benchmark against local Ollama (default phi3:mini).

Loads ``prompts.json``, POSTs each case to ``/api/chat``, compares parsed JSON
``intent`` to golden ``expected.intent``. Writes JSON + optional Markdown report.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PROMPTS = Path(__file__).resolve().parent / "prompts.json"


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort JSON object parse from model output (handles fences / prose)."""
    t = (text or "").strip()
    if not t:
        return None
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t, re.I)
    if fence:
        t = fence.group(1).strip()
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    blob = t[start : end + 1]
    try:
        out = json.loads(blob)
        return out if isinstance(out, dict) else None
    except json.JSONDecodeError:
        return None


def format_classifier_user(raw_user: str, intents: list[str]) -> str:
    return (
        "Allowed intents (choose exactly one for the JSON field intent):\n"
        + json.dumps(intents, indent=0)
        + "\n\nUser message to classify:\n"
        + (raw_user or "").strip()
    )


@dataclass
class CaseResult:
    case_id: str
    category: str
    user: str
    expected_intent: str
    predicted_intent: str | None
    raw_reply: str
    latency_ms: float
    match: bool
    error: str | None = None


@dataclass
class RunSummary:
    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[CaseResult] = field(default_factory=list)
    model: str = ""
    base_url: str = ""

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return 100.0 * self.passed / self.total


def _ollama_chat(
    *,
    base_url: str,
    model: str,
    system: str,
    user: str,
    timeout: float,
) -> tuple[str, float]:
    url = f"{base_url.rstrip('/')}/api/chat"
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "options": {"temperature": 0.0},
    }
    t0 = time.perf_counter()
    with httpx.Client(timeout=timeout) as client:
        r = client.post(url, json=body)
        r.raise_for_status()
        data = r.json()
    dt = (time.perf_counter() - t0) * 1000.0
    msg = data.get("message") if isinstance(data, dict) else None
    if isinstance(msg, dict):
        return str(msg.get("content") or "").strip(), dt
    return str(data.get("response") or "").strip(), dt


def run_ollama_benchmark(
    *,
    prompts_path: Path,
    base_url: str,
    model: str,
    timeout: float,
) -> RunSummary:
    spec = json.loads(prompts_path.read_text(encoding="utf-8"))
    system = str(spec.get("system") or "")
    intents = spec.get("intents")
    if not isinstance(intents, list) or not all(isinstance(x, str) for x in intents):
        raise ValueError("prompts.json: missing or invalid 'intents' list")
    cases = spec.get("cases")
    if not isinstance(cases, list):
        raise ValueError("prompts.json: missing 'cases' array")

    summary = RunSummary(model=model, base_url=base_url)
    for c in cases:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or "")
        cat = str(c.get("category") or "unknown")
        user_raw = str(c.get("user") or "")
        exp = c.get("expected") if isinstance(c.get("expected"), dict) else {}
        exp_intent = str((exp or {}).get("intent") or "")

        user_block = format_classifier_user(user_raw, intents)
        err: str | None = None
        raw = ""
        lat = 0.0
        pred: str | None = None
        ok = False
        try:
            raw, lat = _ollama_chat(
                base_url=base_url,
                model=model,
                system=system,
                user=user_block,
                timeout=timeout,
            )
            parsed = extract_json_object(raw)
            if parsed is None:
                err = "no_json_object"
            else:
                pred = str(parsed.get("intent") or "").strip().lower()
                ok = pred == exp_intent.strip().lower()
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:500]
            ok = False

        summary.results.append(
            CaseResult(
                case_id=cid,
                category=cat,
                user=user_raw,
                expected_intent=exp_intent,
                predicted_intent=pred,
                raw_reply=raw[:2000],
                latency_ms=lat,
                match=ok,
                error=err,
            )
        )
        summary.total += 1
        if ok:
            summary.passed += 1
        else:
            summary.failed += 1

    return summary


def write_json_report(path: Path, summary: RunSummary, extra: dict[str, Any]) -> None:
    payload = {
        "model": summary.model,
        "base_url": summary.base_url,
        "total": summary.total,
        "passed": summary.passed,
        "failed": summary.failed,
        "accuracy_percent": round(summary.accuracy, 2),
        **extra,
        "results": [
            {
                "id": r.case_id,
                "category": r.category,
                "user": r.user,
                "expected_intent": r.expected_intent,
                "predicted_intent": r.predicted_intent,
                "match": r.match,
                "latency_ms": round(r.latency_ms, 2),
                "error": r.error,
                "raw_reply_preview": r.raw_reply[:500],
            }
            for r in summary.results
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown_report(path: Path, summary: RunSummary) -> None:
    lines = [
        "# Agent-task intent benchmark",
        "",
        f"- **Model:** `{summary.model}`",
        f"- **Base URL:** `{summary.base_url}`",
        f"- **Total:** {summary.total}",
        f"- **Passed:** {summary.passed}",
        f"- **Failed:** {summary.failed}",
        f"- **Accuracy:** {summary.accuracy:.2f}%",
        "",
        "| id | expected | predicted | match | ms |",
        "|----|----------|-----------|-------|-----|",
    ]
    for r in summary.results:
        pred = r.predicted_intent or "—"
        lines.append(
            f"| {r.case_id} | {r.expected_intent} | {pred} | {'yes' if r.match else 'no'} | {r.latency_ms:.0f} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent-task intent benchmark (Ollama or oracle).")
    parser.add_argument(
        "--prompts",
        type=Path,
        default=_PROMPTS,
        help="Path to prompts.json",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434", help="Ollama root URL")
    parser.add_argument("--model", default="", help="Override model (default from prompts.json)")
    parser.add_argument("--timeout", type=float, default=120.0, help="HTTP timeout seconds")
    parser.add_argument("--json-out", type=Path, default=None, help="Write machine-readable report")
    parser.add_argument("--markdown-out", type=Path, default=None, help="Write Markdown table report")
    args = parser.parse_args()

    if not args.prompts.is_file():
        print(f"Missing prompts file: {args.prompts}", file=sys.stderr)
        return 2

    spec = json.loads(args.prompts.read_text(encoding="utf-8"))
    model = (args.model or "").strip() or str(spec.get("ollama_model") or "phi3:mini")
    summary = run_ollama_benchmark(
        prompts_path=args.prompts,
        base_url=args.base_url,
        model=model,
        timeout=args.timeout,
    )
    extra: dict[str, Any] = {"mode": "ollama"}

    print(
        f"Benchmark ollama: {summary.passed}/{summary.total} passed "
        f"({summary.accuracy:.2f}%)"
    )

    if args.json_out:
        write_json_report(args.json_out, summary, extra)
        print(f"Wrote JSON: {args.json_out}")
    if args.markdown_out:
        write_markdown_report(args.markdown_out, summary)
        print(f"Wrote Markdown: {args.markdown_out}")

    return 0 if summary.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
    """Best-effort JSON object parse from model output (handles fences / prose after JSON)."""
    t = (text or "").strip()
    if not t:
        return None
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", t, re.I)
    if fence:
        t = fence.group(1).strip()
    start = 0
    while True:
        start = t.find("{", start)
        if start == -1:
            return None
        depth = 0
        end_idx = -1
        for i in range(start, len(t)):
            c = t[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx == -1:
            return None
        blob = t[start : end_idx + 1]
        try:
            out = json.loads(blob)
            if isinstance(out, dict):
                return out
        except json.JSONDecodeError:
            start += 1
            continue
        start += 1


def build_intent_classifier_system_prompt(base_instruction: str) -> str:
    """Append few-shot examples (addresses common small-model mislabels; tuned for Qwen/Phi)."""
    base = (base_instruction or "").strip()
    shots = """
## Critical disambiguation (read before classifying)
- **greeting**: short social openers only (hi, hello, hey, good morning, howdy) with **no** real task yet. **Never** use general_chat for these.
- **general_chat**: trivia, small talk, factual Q&A, or chit-chat that is **not** a greeting-only line and **not** another intent.
- **brain_dump**: user lists **2+ concrete tasks/errands** or clear multi-item todo language — not a single imperative dev command. **Release-engineering checklists** (ship patch, changelog, tag, tests) are **brain_dump** unless they explicitly demand a **hosted** fix-push-verify **pipeline** (Railway/Render/production) — then **external_execution**.
- **create_sub_agent**: user wants a **named role/specialist agent** (marketing, QA, security, research, …) via registry — phrases like "create a … agent", "spawn a … agent", "I need a … specialist".
- **create_custom_agent**: legacy **user-defined agent profile** wording only when clearly about building a **custom profile/config**, not a role specialist (rare in benchmarks).
- **orchestrate_system**: status across **missions / Mission Control / dev runs / what succeeded or failed** — orchestration overview.
- **external_execution**: user wants an **end-to-end pipeline** on **hosted** infra (check logs, fix, push, redeploy, **verify production** / explicit hosted service). **Not** a simple local task list without hosted verification language.
- **external_execution_continue**: short confirmation continuing a prior **external execution / Railway / deploy** access thread.
- **external_investigation**: hosted provider health / outage / dashboard questions **without** demanding the full fix-push-verify pipeline.
- **stuck**: emotional **freeze / overwhelm about life or work in general** without a concrete task list or “not done yet” deferral.
- **followup_reply**: user reports **incomplete work** on something already in motion (“I didn’t finish”, “not done yet”, “still working on it”) — **not** stuck unless it is clearly emotional overwhelm, not task status. **Not** status_update: followup is about **incomplete** progress, not **done**.
- **status_update**: user reports **completed** or **done** work (“I finished…”, “completed the migration”, “shipped it yesterday”).
- **correction**: user **rejects** the assistant’s prior answer or demands it answer differently (“No, answer the question”, “you misunderstood”).
- **clarification**: vague product tweak with **no URL/stack/concrete goal** (“make my website better”, “improve my app”) — **not** help_request when the user is asking how to decide what to do next. **Not** analysis: **postmortem / root-cause / “analyze this [paste, trace, summary]”** on supplied material → **analysis**, not a vague tweak.
- **analysis**: asks for a **structured writeup or diagnosis of supplied material** — **postmortem**/RCA on an outage summary, “**analyze this** stack trace / log / document”. **Not** when the user is mainly **reporting a live project failure** (TypeError in code, eslint/pytest/CI failures) → that is **stuck_dev**.
- **help_request**: user wants **support, guidance, or help figuring out next steps** (“I need help”, “not sure what to ask”, “help me figure out what to do next”) — **not** greeting (no hi/hello opener required) and **not** clarification unless the message is **only** a vague product tweak with zero help-seeking.
- **config_query**: asks about **this deployment’s** configuration (which LLM, workspace path, whether keys are set — never the secret values).
- **capability_question**: asks what the assistant **can or cannot do** in a domain (“can you deploy”, “do you support agents”) — not “run npm test” style imperative.
- **dev_command**: imperative **run / show / print** (“run npm test”, “git status”) — **not** “tool X **fails** / **error** …” (those are **stuck_dev** failure reports, not commands).
- **stuck_dev**: **build, test, CI, lint, deploy, tooling** — user’s project is **broken or red** (TypeError, failing tests, eslint errors, CI red). Prefer **stuck_dev** over **analysis** when the line **reports a failure** rather than asking to postmortem/analyze a pasted artifact.

## Few-shot (your entire reply must be ONE JSON object only — no markdown, no text before or after)
User message: hello there
{"intent":"greeting","confidence":0.95,"reason":"short social opener"}

User message: hey team
{"intent":"greeting","confidence":0.92,"reason":"greeting to group"}

User message: buy milk, call dentist, finish the deck slides
{"intent":"brain_dump","confidence":0.9,"reason":"multiple concrete tasks listed"}

User message: create a marketing agent for me
{"intent":"create_sub_agent","confidence":0.9,"reason":"registry role specialist"}

User message: spawn a QA specialist agent
{"intent":"create_sub_agent","confidence":0.9,"reason":"spawn specialist"}

User message: give me mission control status on all runs
{"intent":"orchestrate_system","confidence":0.88,"reason":"orchestration status"}

User message: check railway logs, fix the code, push, redeploy, verify production
{"intent":"external_execution","confidence":0.9,"reason":"full hosted pipeline"}

User message: yes use the railway token I pasted
{"intent":"external_execution_continue","confidence":0.85,"reason":"continues deploy access thread"}

User message: is railway down for everyone right now
{"intent":"external_investigation","confidence":0.85,"reason":"hosted service health question"}

User message: I feel completely stuck and can't start
{"intent":"stuck","confidence":0.88,"reason":"overwhelm without task list"}

User message: pytest fails with a fixture error on CI
{"intent":"stuck_dev","confidence":0.9,"reason":"technical CI/test failure"}

User message: TypeError in my FastAPI route handler
{"intent":"stuck_dev","confidence":0.9,"reason":"runtime error in user code"}

User message: eslint fails with no-unused-vars
{"intent":"stuck_dev","confidence":0.9,"reason":"lint failure not an imperative command"}

User message: I didn't finish the task yet
{"intent":"followup_reply","confidence":0.9,"reason":"incomplete work update"}

User message: not done yet
{"intent":"followup_reply","confidence":0.88,"reason":"short deferral on progress"}

User message: No, answer the question I asked
{"intent":"correction","confidence":0.92,"reason":"rejects prior answer"}

User message: you misunderstood my request
{"intent":"correction","confidence":0.9,"reason":"meta correction"}

User message: make my website better
{"intent":"clarification","confidence":0.85,"reason":"vague product ask"}

User message: analyze this stack trace and root cause it
{"intent":"analysis","confidence":0.9,"reason":"structured technical diagnosis"}

User message: postmortem this outage summary
{"intent":"analysis","confidence":0.9,"reason":"incident postmortem is structured analysis"}

User message: what model are you using
{"intent":"config_query","confidence":0.9,"reason":"deployment LLM settings"}

User message: can you write code for me
{"intent":"capability_question","confidence":0.88,"reason":"asks if coding is supported"}

User message: run npm test in the repo root
{"intent":"dev_command","confidence":0.9,"reason":"imperative command"}

User message: ship the patch, update the changelog, and tag the release
{"intent":"brain_dump","confidence":0.9,"reason":"multi-item local release checklist not hosted pipeline"}

User message: I need help but I'm not sure what to ask
{"intent":"help_request","confidence":0.88,"reason":"seeks guidance not a greeting"}

User message: I finished the migration yesterday
{"intent":"status_update","confidence":0.92,"reason":"reports completed work"}

User message: help me figure out what to do next
{"intent":"help_request","confidence":0.88,"reason":"next-step guidance not vague product tweak"}
""".strip()
    return f"{base}\n\n{shots}".strip()


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
    base_system = str(spec.get("system") or "")
    system = build_intent_classifier_system_prompt(base_system)
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
    parser.add_argument("--timeout", type=float, default=180.0, help="HTTP timeout seconds (per request)")
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

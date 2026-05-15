# OpenClaw parity audit — AethOS Phase 1

This document is the controlling parity audit for AethOS.

## Objective

AethOS must reproduce OpenClaw exactly as it works today before the project prioritizes privacy, PII filtering, local-first differentiation, cost transparency, or custom AethOS-specific architecture.

Phase 1 is complete only when OpenClaw-equivalent workflows can be installed, configured, run, tested, and demonstrated without relying on future Phase 2 differentiators.

## Hard rule

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

When a tradeoff appears between OpenClaw parity and AethOS differentiation, choose parity until Phase 1 is verified.

## Status language

| Status | Meaning |
| --- | --- |
| Done | Behavior is implemented and has parity verification. |
| Partial | Surface exists but behavior is incomplete, unverified, or weaker than OpenClaw. |
| Missing | No meaningful implementation yet. |
| Deferred | Intentionally not Phase 1, unless needed for parity. |

---

## 1. Agent orchestration parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Natural language gateway | Partial | Gateway paths exist, but exact OpenClaw conversational routing needs reference workflow comparison. | Capture OpenClaw reference prompts and add regression tests. |
| Specialist creation/orchestration | Partial | Dynamic agent surfaces exist. | Verify lifecycle, delegation, and output format against OpenClaw. |
| Multi-agent coordination | Partial | Missions/concurrency vary by workload. | Add tests for parallel/sub-agent task routing. |
| Long-lived agents | Partial | Long-running session module and scheduler hooks exist. | Verify continuation, checkpoints, and resume semantics. |

## 2. Tool execution parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| File operations | Partial | Scoped reads/writes exist. | Compare exact permissions, UX, and failure behavior. |
| Shell execution | Partial | Allowlisted command execution exists. | Match OpenClaw command lifecycle, logs, approvals, and failures. |
| Browser/tool use | Partial | Browser preview/Playwright paths are gated. | Match OpenClaw browser workflows behind equivalent flags. |
| Deploy helpers | Partial | Vercel/Railway/Fly and generic deploy paths exist when tokens/CLIs are configured. | Add parity scenario tests for deploy listing and launch flows. |

## 3. Mission Control/UI parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Web operator UI | Partial | Next.js Mission Control exists. | Map screens and flows to OpenClaw reference UI. |
| Connection/auth setup | Partial | User ID and bearer token localStorage flow exists. | Verify first-run setup and token UX. |
| Run visibility | Partial | Status and health surfaces exist. | Ensure OpenClaw-like mission/run timeline visibility. |
| Operator controls | Partial | Pause/resume/cancel API surfaces exist. | Ensure executor honors controls consistently. |

## 4. Memory/context parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Durable user memory | Partial | Markdown/JSON store paths exist. | Validate save/retrieve/update semantics. |
| Semantic search | Partial | Pseudo/optional embedding paths exist. | Match OpenClaw retrieval quality or document gap. |
| Mission summaries | Partial | Intelligence pass and summaries exist in places. | Add workflow tests for automatic summary creation/use. |
| Context continuity | Partial | Needs reference test coverage. | Add cross-session continuity tests. |

## 5. Provider/model routing parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Cloud providers | Partial | Provider keys and routing settings exist. | Verify exact fallback and failure behavior. |
| Local model paths | Partial | Ollama/local flags exist. | Keep from changing OpenClaw-compatible defaults unless required. |
| LLM-first gateway | Partial | `NEXA_LLM_FIRST_GATEWAY` exists. | Make default parity mode explicit in setup docs/wizard. |
| Token/cost behavior | Deferred | Useful Phase 2 differentiator, but should not block OpenClaw parity. | Keep non-blocking during Phase 1 unless OpenClaw-compatible. |

## 6. Channels parity

| Channel | Status | Notes | Next action |
| --- | --- | --- | --- |
| Web | Partial | Mission Control + API exist. | Verify full operator workflows. |
| Telegram | Partial | Bot path and optional embed mode exist. | Verify single-poller behavior and gateway routing. |
| Slack | Partial | Adapter/socket mode surfaces exist. | Verify token setup and inbound routing. |
| Discord | Partial | Adapter foundation exists. | Verify bot intents and routing. |
| WhatsApp | Partial | Webhook/channel gateway surfaces exist. | Verify end-to-end behavior or mark non-parity. |

## 7. Install/setup parity

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| One-curl install | Partial | Root `install.sh` exists. | Verify fresh-machine success. |
| Setup wizard | Partial | `scripts/setup.sh` / `scripts/setup.py` path exists. | Ensure defaults support parity-first mode. |
| Manual install | Partial | Docs exist. | Keep docs in sync with actual commands. |
| Docker/Postgres | Partial | Compose files exist. | Verify production-like path. |
| Doctor/smoke checks | Partial | Scripts/tests exist. | Add parity checklist output. |

---

## Phase 1 priority backlog

1. Build a reference OpenClaw workflow matrix with expected behavior, prompts, UI states, tool calls, and outputs.
2. Convert the matrix into automated or repeatable manual tests.
3. Make gateway, agent orchestration, tool execution, and Mission Control defaults match the reference.
4. Strengthen `tests/test_openclaw_parity.py` around real parity workflows, not only surface existence.
5. Keep every gap visible in this audit until closed.

## Phase 2 backlog

Only after Phase 1 is verified:

1. Privacy and PII filtering improvements.
2. Stronger local-first execution.
3. Cost transparency and budgeting improvements.
4. Safety-layer redesigns and stronger isolation.
5. AethOS-specific UX, orchestration, and marketplace differentiation.

---

## Required PR note

Every parity PR must include:

```text
OpenClaw behavior reproduced:
Parity checkpoint advanced:
Verification performed:
Remaining divergence:
```

---

See also: [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md), [MIGRATING_FROM_OPENCLAW.md](MIGRATING_FROM_OPENCLAW.md), [OPENCLAW_SUCCESSOR_AUDIT.md](OPENCLAW_SUCCESSOR_AUDIT.md), and `tests/test_openclaw_parity.py`.

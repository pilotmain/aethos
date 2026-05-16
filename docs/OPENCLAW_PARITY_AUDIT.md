# OpenClaw parity audit — AethOS Phase 1

This document is the controlling parity audit for AethOS.

## Objective

AethOS must reproduce OpenClaw exactly as it works today before the project prioritizes privacy, PII filtering, local-first differentiation, cost transparency, or custom AethOS-specific architecture.

Phase 1 is complete only when OpenClaw-equivalent workflows can be installed, configured, run, tested, and demonstrated without relying on future Phase 2 differentiators.

## Master implementation plan

Priorities **P1–P4**, required **CLI** surfaces (`aethos onboard`, `aethos gateway`, `aethos message send`, `aethos status`, `aethos logs`, `aethos doctor`), workspace layout targets, and the parity **test file matrix** are defined in **[OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md)**. This audit tracks **gaps**; the directive defines **scope and execution order**.

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

## 8. Persistent runtime parity (`~/.aethos/aethos.json`)

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Canonical runtime JSON | Partial | `app/runtime/*` loads/saves atomic `aethos.json`; FastAPI lifespan hooks when not in pytest. | Wire richer session/agent/deployment mirrors from DB where applicable. |
| Workspace + logs dirs | Partial | `~/.aethos/workspace`, `~/.aethos/logs` ensured on boot. | Persist execution artifacts + structured log files. |
| Gateway heartbeat | Partial | Background thread updates `gateway.last_heartbeat`. | Tune intervals; avoid races with multi-worker. |
| Stale PID recovery | Partial | `reconcile_stale_gateway_pid` clears dead `gateway.pid`. | Harden multi-instance / container edge cases. |
| Heartbeat / runtime tests | Partial | `tests/test_openclaw_runtime_*.py` added. | Replace thin checks with full restart / recovery scenarios. |

---

## 9. Orchestration runtime parity (`app/orchestration/` + `aethos.json`)

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Task registry + task states | Partial | `task_registry` dict; states include `queued`…`recovering` per OpenClaw Phase 1 list. | Wire real task producers (gateway, agents) into registry. |
| Named persistent queues | Partial | Six queues merged on load; `execution_queue` + legacy `tasks` coexist. | Drive `agent_queue` / `channel_queue` / `scheduler_queue` from real inbound events. |
| Boot recovery | Partial | `running` / `waiting` / `retrying` → `recovering` + `recovery_queue`. | Expand deployment/session/agent recovery per reference matrix. |
| Scheduler + dispatcher | Partial | Background thread ticks (`AETHOS_ORCHESTRATION_TICK_SEC`); `dispatch_once` concurrency 1; recovery queue before execution queue; **plan-driven tasks** re-queued until multi-step completion. | Concurrency limits, starvation guards, richer deploy/channel drivers. |
| Checkpoints | Partial | `orchestration.checkpoints` for noop/deploy completions. | Persist partial outputs for long-running steps. |
| Structured logs | Partial | JSON lines to `~/.aethos/logs/{orchestration,runtime,recovery,agents,deployments,gateway}.log` via append helpers. | Emit gateway events from gateway lifecycle code paths. |
| CLI visibility | Partial | `aethos status` prints scheduler/queue/task/deploy summaries; `doctor` checks queue/registry/checkpoint/scheduler shapes + prunes orphan queue refs; `logs orchestration\|recovery`. | Add `session_count` when session model is unified. |
| Tests | Partial | Eight new `tests/test_openclaw_*.py` modules (registry, scheduler, queues, checkpoints, agents, orchestration recovery, deployment dispatch, dispatcher). | Add integration tests with real API boot when stable. |

---

## 10. Autonomous execution parity (`app/execution/` + `aethos.json`)

| Feature | Status | Notes | Next action |
| --- | --- | --- | --- |
| Execution plans + DAG | Partial | `execution.plans` with `steps` (`step_id`, `depends_on`, `blocked`/`queued`/`running`/`completed`/`retrying`/`failed`). | Wire gateway/agents to emit real graphs. |
| Retry runtime | Partial | `retry_count`, `last_retry_at`, `next_retry_at` (unix), exponential backoff cap 300s, `retries.log`. | Backoff jitter; max retry policy; fail terminal. |
| Checkpoints + memory | Partial | `execution.checkpoints[plan_id][step_id]`; `execution.memory[task_id]` outputs + continuation. | Richer partial outputs / reasoning blobs. |
| Execution supervisor | Partial | One step per tick; `execution.supervisor` ticks; unblocks dependents after step completion. | Stalled detection, parallel ready steps. |
| Boot continuation | Partial | `recover_execution_on_boot` resets interrupted `running` steps; `deployment_recovery` marker on deploy plans. | Full deployment stage machine + log tail persistence. |
| Execution chains | Partial | `execution.chains` linear cursor for multi-task sequences. | Cross-task deps + orchestration routing. |
| Structured logs | Partial | `execution.log`, `checkpoints.log`, `retries.log`, `scheduler.log` (scheduler tick mirrors). | Correlate with gateway PID lifecycle. |
| CLI | Partial | `status` / `doctor` / `logs` extended for execution metrics + integrity. | Mission Control JSON feeds (no UI redesign). |
| Tests | Partial | `tests/test_openclaw_execution_*.py` + `test_openclaw_autonomous_execution.py`. | Long-running hour-scale scenarios. |

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

## Phase 1 operational confidence lock

Phase 1 architecture/runtime parity is treated as **complete**; remaining work is **certification, consistency, boundedness, and operational trustworthiness** (see [OPENCLAW_FINAL_PARITY_AUDIT.md](OPENCLAW_FINAL_PARITY_AUDIT.md), including **Phase 1 final operational certification (closure)** for suite totals and boundedness metrics). Additive tests only: `tests/production_like/` (churn, **≥100**-cycle gates, boundedness observed-maxima certification, save/load cycles, deployment/rollback/lock integrity), `tests/edge_cases/`, `tests/soak/`, `tests/openclaw_behavioral_validation/`, `tests/parity_freeze_gate.py`, and `tests/test_openclaw_{reliability,continuity,warning}_consistency.py` / snapshot / CLI visibility freeze tests for deterministic reads.

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

See also: [PROJECT_HANDOFF.md](../PROJECT_HANDOFF.md), [OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md), [MIGRATING_FROM_OPENCLAW.md](MIGRATING_FROM_OPENCLAW.md), [OPENCLAW_SUCCESSOR_AUDIT.md](OPENCLAW_SUCCESSOR_AUDIT.md), `tests/test_openclaw_parity.py`, `tests/test_openclaw_*_parity.py`, `tests/test_openclaw_runtime_*.py`, orchestration tests (`tests/test_openclaw_task_*.py`, `tests/test_openclaw_scheduler.py`, `tests/test_openclaw_queue_*.py`, `tests/test_openclaw_agent_runtime.py`, `tests/test_openclaw_orchestration_recovery.py`, `tests/test_openclaw_deployment_recovery.py`, `tests/test_openclaw_runtime_dispatcher.py`), and autonomous execution tests (`tests/test_openclaw_execution_*.py`, `tests/test_openclaw_autonomous_execution.py`).

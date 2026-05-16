# AethOS — OpenClaw functional parity implementation status

Canonical policy and scope: [OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md).  
This document is a **point-in-time implementation status** snapshot (update when milestones land).

---

## Repository state

| Item | Status |
| --- | --- |
| Branch | `main` (pushed) |
| Baseline (doctrine + CLI surface) | `76f7d65` |
| Persistent runtime slice | `7c9d014` — `app/runtime/`, `~/.aethos/aethos.json`, lifespan + heartbeat (skipped under `NEXA_PYTEST` unless `AETHOS_RUNTIME_ENABLE_IN_PYTEST=1`) |
| Orchestration runtime slice | `app/orchestration/` — persistent `task_registry` + named queues + boot recovery + background scheduler/dispatcher (skipped under `NEXA_PYTEST` unless `AETHOS_ORCHESTRATION_ENABLE_IN_PYTEST=1`; tick `AETHOS_ORCHESTRATION_TICK_SEC`) |
| Autonomous execution slice | `app/execution/` — persistent `execution.plans` (DAG steps), retries/backoff, `execution.checkpoints` + memory, supervisor ticks, boot step resume; dispatcher re-queues in-flight plan tasks |
| Follow-up | `73ba225` — Cursor rule: prefer commit + push to `main` when slices are done |

### Verification (reported green)

| Check | Result |
| --- | --- |
| `python -m compileall -q app aethos_cli` | Success |
| Parity tests (`tests/test_openclaw_*_parity.py` + `tests/test_openclaw_parity.py`) | Passing |
| Runtime persistence tests (`tests/test_openclaw_runtime_*.py`) | Passing |
| Orchestration runtime tests (`tests/test_openclaw_task_*.py`, `tests/test_openclaw_scheduler.py`, `tests/test_openclaw_queue_*.py`, `tests/test_openclaw_agent_runtime.py`, `tests/test_openclaw_orchestration_recovery.py`, `tests/test_openclaw_deployment_recovery.py`, `tests/test_openclaw_runtime_dispatcher.py`) | Passing |
| Autonomous execution tests (`tests/test_openclaw_execution_*.py`, `tests/test_openclaw_autonomous_execution.py`) | Passing |
| Doctrine tests (`tests/test_openclaw_doctrine_docs.py`) | Passing |
| Phase 1 confidence + **transition gate** (`tests/parity_freeze_gate.py`, `tests/production_like/`, `tests/edge_cases/`, snapshot + CLI freeze tests) | Passing (see [OPENCLAW_FINAL_PARITY_AUDIT.md](OPENCLAW_FINAL_PARITY_AUDIT.md)) |
| CLI parity surface | Operational (`aethos onboard`, `gateway`, `message send`, `status`, `logs`, `doctor`) |

---

## 1. Master plan document

**Added:** [OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md)

**Contains:** project objectives; non-negotiable parity rule; Phase 1 parity requirements (gateway, CLI, orchestration, tools, deployment, memory, Mission Control, multi-agent); Phase 2 deferred work; forbidden divergence; PR review rules; required parity test module names; documentation alignment; implementation priorities P1–P4; final branding vs capability directive.

**Doctrine rule (verbatim):** Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

**Doctrine coverage:** OpenClaw **functionality** parity first; **AethOS** branding retained; privacy / PII / local-first deferred to Phase 2 unless required for OpenClaw-compatible behavior; **capability** parity over branding parity.

---

## 2. CLI functional parity

**Updated files:** `aethos_cli/__main__.py`, `aethos_cli/parity_cli.py`

| Command | Purpose |
| --- | --- |
| `aethos onboard` | Interactive setup / onboarding parity → maps to **setup** workflow |
| `aethos gateway` | Persistent HTTP gateway parity → **uvicorn** `app.main:app` (`--host`, `--port`, `--reload`) |
| `aethos message send` | Gateway message execution parity → `POST /api/v1/mission-control/gateway/run` |
| `aethos status` | HTTP health + **persistent runtime** summary from `~/.aethos/aethos.json` when present + **orchestration** + **autonomous execution** (graphs, retrying steps/tasks, checkpoint counts, supervisor ticks, recovery events) |
| `aethos logs` | Tail logs; optional category `gateway\|agents\|deployments\|runtime\|orchestration\|recovery\|execution\|checkpoints\|retries\|scheduler` (`runtime` tails `aethos.json`); `--lines N` |
| `aethos doctor` | `compileall` on `app` + `aethos_cli`, runtime/workspace + **orchestration** + **execution graph / checkpoint / retry integrity**, orphan plan prune, stalled hints, optional `GET /api/v1/health` |

---

## 3. Parity test matrix

**New modules:**

| File | Verifies (initial thin checks) |
| --- | --- |
| `tests/test_openclaw_cli_parity.py` | `-h` lists `onboard`, `gateway`, `message`, `status`, `logs`, `doctor`; `message send -h` |
| `tests/test_openclaw_gateway_parity.py` | `nexa_llm_first_gateway` on `Settings` |
| `tests/test_openclaw_workspace_parity.py` | `get_aethos_data_dir().name == "data"` |
| `tests/test_openclaw_agent_parity.py` | `DEV_PIPELINE_SEQUENCE` |
| `tests/test_openclaw_memory_parity.py` | `MemoryStore` empty list |
| `tests/test_openclaw_tool_parity.py` | `is_command_safe("echo …")` |
| `tests/test_openclaw_deployment_parity.py` | `parse_deploy_intent("deploy")` |
| `tests/test_openclaw_channel_parity.py` | `route_inbound` web |
| `tests/test_openclaw_runtime_persistence.py` | `aethos.json` round-trip |
| `tests/test_openclaw_gateway_recovery.py` | Stale gateway PID recovery |
| `tests/test_openclaw_session_recovery.py` | Session rows in runtime JSON |
| `tests/test_openclaw_workspace_persistence.py` | `~/.aethos/workspace` created |
| `tests/test_openclaw_runtime_registry.py` | `get_runtime_snapshot()` |
| `tests/test_openclaw_heartbeat.py` | Heartbeat updates `last_heartbeat` |
| `tests/test_openclaw_long_running_tasks.py` | `tasks` / `execution_queue` / `long_running` shell lists |
| `tests/test_openclaw_task_registry.py` | `task_registry` persistence + state machine |
| `tests/test_openclaw_task_checkpointing.py` | `orchestration.checkpoints` after noop dispatch |
| `tests/test_openclaw_scheduler.py` | Scheduler thread advances ticks + completes queued noop |
| `tests/test_openclaw_queue_recovery.py` | Boot recovery + orphan queue prune |
| `tests/test_openclaw_agent_runtime.py` | Agent registry + delegated/active task lists |
| `tests/test_openclaw_orchestration_recovery.py` | `running` → `recovering` + `recovery_queue` |
| `tests/test_openclaw_deployment_recovery.py` | `deploy` task checkpoint + `deployments` row |
| `tests/test_openclaw_runtime_dispatcher.py` | Recovery queue precedence |
| `tests/test_openclaw_execution_plans.py` | `execution.plans` + subtasks + deps persist |
| `tests/test_openclaw_execution_chains.py` | `execution.chains` cursor + completion |
| `tests/test_openclaw_execution_retry.py` | Exponential backoff + retry fields persist |
| `tests/test_openclaw_execution_recovery.py` | Boot resets `running` steps → `queued` |
| `tests/test_openclaw_execution_dependencies.py` | DAG validation + dependency ordering |
| `tests/test_openclaw_execution_checkpointing.py` | `execution.checkpoints` round-trip |
| `tests/test_openclaw_execution_supervisor.py` | Multi-step plan completes via supervisor |
| `tests/test_openclaw_autonomous_execution.py` | Dispatcher re-queue until plan completes |

**Preserved unchanged:** `tests/test_openclaw_parity.py`

**Example aggregate run:**

```bash
pytest tests/test_openclaw_doctrine_docs.py tests/test_openclaw_*_parity.py tests/test_openclaw_runtime_*.py tests/test_openclaw_task_*.py tests/test_openclaw_scheduler.py tests/test_openclaw_queue_*.py tests/test_openclaw_agent_runtime.py tests/test_openclaw_orchestration_recovery.py tests/test_openclaw_deployment_recovery.py tests/test_openclaw_runtime_dispatcher.py tests/test_openclaw_execution_*.py tests/test_openclaw_autonomous_execution.py tests/test_openclaw_parity.py -q
```

(Previously reported: **21** parity + **9** runtime-related checks on a healthy checkout; counts vary as tests are added.)

---

## 4. Documentation and Cursor rules

**Touched / aligned:** `PROJECT_HANDOFF.md`, `docs/OPENCLAW_PARITY_AUDIT.md`, `README.md`, `CONTRIBUTING.md`, `docs/README.md`, `docs/development/contributing.md`, `.cursor/rules/openclaw-parity-first.mdc`, `docs/MIGRATING_FROM_OPENCLAW.md`, `tests/test_openclaw_doctrine_docs.py` (directive file in doctrine list).

**Cursor:** `.cursor/rules/openclaw-parity-first.mdc` — parity-first enforcement; Phase 1 vs Phase 2 sequencing.

**Optional operator rule:** `.cursor/rules/user-always-commit-push-main.mdc` — prefer commit + push to `main` when slices are complete.

---

## 5. Doctrine tests

`tests/test_openclaw_doctrine_docs.py` requires listed docs to include **OpenClaw parity** language and the **divergence** sentence; `docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md` is in the required file set.

---

## 6. Sample runtime check

```bash
aethos doctor
```

Example output when API is up: `compileall: OK`, `health HTTP 200` for `/api/v1/health`.

---

## 7. Phase 1 — completed vs remaining

### Completed (structural)

- Doctrine and parity governance docs
- CLI parity **surface** (`onboard`, `gateway`, `message send`, `logs`, `doctor`)
- Parity **test framework** (eight `test_openclaw_*_parity.py` modules + existing `test_openclaw_parity.py`)
- **Persistent runtime shell**: `app/runtime/*`, atomic `~/.aethos/aethos.json`, workspace/logs dirs, lifespan boot + heartbeat (skipped under `NEXA_PYTEST` unless `AETHOS_RUNTIME_ENABLE_IN_PYTEST=1`)
- **Orchestration runtime (Phase 1 scaffold)**: `app/orchestration/*` — persistent `task_registry`, named queues (`execution_queue`, `deployment_queue`, `agent_queue`, `channel_queue`, `recovery_queue`, `scheduler_queue`), boot recovery for interrupted tasks, background scheduler + dispatcher (skipped under `NEXA_PYTEST` unless `AETHOS_ORCHESTRATION_ENABLE_IN_PYTEST=1`), structured JSON appenders under `~/.aethos/logs/` (`orchestration`, `runtime`, `recovery`, `agents`, `deployments`, `gateway` stems)
- **Autonomous execution (Phase 1 scaffold)**: `app/execution/*` — `execution.plans` (multi-step DAGs, `blocked`/`queued`/`retrying` semantics), exponential **retry** metadata, `execution.checkpoints` + `execution.memory`, **execution_supervisor** ticks, boot **continuation** (`recover_execution_on_boot` with orchestration boot), dispatcher **re-queue** for in-flight plan tasks; logs `execution.log`, `checkpoints.log`, `retries.log`, `scheduler.log`
- **Runtime persistence tests** (`tests/test_openclaw_runtime_*.py`)
- **Orchestration persistence tests** (task registry, scheduler, queues, checkpoints, agent runtime, recovery, deployment dispatch, dispatcher ordering — see §3 matrix)
- **Autonomous execution tests** (`tests/test_openclaw_execution_*.py`, `tests/test_openclaw_autonomous_execution.py`)
- Expanded **`aethos status` / `logs` / `doctor`** for runtime + orchestration + execution visibility
- Documentation and Cursor alignment with the directive

### Remaining Phase 1 (high level)

| Area | Target |
| --- | --- |
| **Workspace expansion** | Populate `sessions`, `agents`, `deployments`, queues from real orchestration / DB — not only JSON shells |
| **Richer gateway runtime** | Session manager, autonomous loops, long-running coordination, multi-agent execution, channel-driven queues (match OpenClaw reference) |
| **Orchestration + execution depth** | Real tool runs, parallel step workers, richer deployment stages/logs, starvation-safe re-queue, Mission Control read-only APIs (no UI redesign) |
| **Workflow-level tests** | Full multi-minute restart scenarios; gateway + scheduler integration under load |

---

## 8. Strategic direction

**AethOS** is aligned on **OpenClaw functional parity first.**

| In scope | Out of scope for Phase 1 |
| --- | --- |
| Behavior, workflow, orchestration, operator **capability** parity | Branding parity, visual cloning, code copying |
| **AethOS** naming and product identity | Imitating OpenClaw **brand** |

**Capability target:** OpenClaw-equivalent operational power for the operator.

---

*Maintainers: bump the “baseline commit” row when you land the next parity milestone; keep this file honest about what is “done” vs “thin scaffold.”*

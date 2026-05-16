# AethOS — OpenClaw functional parity directive (master implementation plan)

## Core objective

AethOS must achieve the **same functionality, workflows, operator experience, and autonomous capabilities** as OpenClaw as it exists today.

This is **not** a branding clone and **not** a code copy exercise.

The objective is:

- reproduce OpenClaw **behavior**
- reproduce OpenClaw **workflows**
- reproduce OpenClaw **operational capabilities**
- reproduce OpenClaw **user outcomes**
- reproduce OpenClaw **orchestration patterns**
- reproduce OpenClaw **deployment and gateway experience**

while preserving:

- AethOS **branding** and **naming**
- Python / FastAPI implementation where beneficial
- AethOS **internal architecture** where possible

---

## Non-negotiable project rule

**OpenClaw parity** is measured by operator-visible behavior and workflows, not labels.

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

All roadmap, architecture, and implementation decisions must answer:

**Does this move AethOS closer to OpenClaw functional parity?**

If the answer is no: **defer it**, **gate it**, **remove it**, or **postpone it until Phase 2**.

---

## What must match OpenClaw

AethOS should behave like OpenClaw from the **operator** perspective. The following areas are mandatory parity targets.

Naming stays **AethOS** (e.g. `aethos gateway`, not `openclaw gateway`). **Behavior** parity matters; **naming** parity does not.

---

## Phase 1 — exact functional parity

### 1. Gateway behavior parity

- Persistent assistant gateway, always-on orchestration, real-time command routing
- Channel-aware handling, multi-session routing, autonomous execution loops
- Persistent operator context

### 2. CLI workflow parity

Required **AethOS** commands (workflows equivalent to OpenClaw):

| Command | Role |
| --- | --- |
| `aethos onboard` | First-time / operator onboarding |
| `aethos gateway` | Run the persistent HTTP gateway (uvicorn stack) |
| `aethos message send` | Dispatch a message through the mission gateway |
| `aethos status` | Operator / connectivity status |
| `aethos logs` | Recent gateway / local logs |
| `aethos doctor` | Diagnostics (health, imports, quick sanity) |

### 3. Workspace parity

Canonical layout (extend as implementation lands):

- `~/.aethos/`, `~/.aethos/workspace/`, `~/.aethos/logs/`, `~/.aethos/aethos.json` (or equivalent single config surface)

Parity targets: persistent sessions, context, tool state, memory continuity, execution history, local runtime state.

### 4. Agent orchestration parity

Autonomous loops, long-running execution, multi-agent coordination, tool chaining, memory-aware execution, session continuation, interrupt/resume, deployment + shell + workspace operations.

### 5. Tool execution parity

Shell, file editing, workspace manipulation, deployments, environment handling, autonomous commands, session state, long-running tasks, gateway-triggered actions.

### 6. Mission Control / operator UX parity

Live sessions, active tasks, gateway state, execution logs, memory inspection, deployment monitoring, tool and autonomous visibility — **capability** parity, not pixel-perfect UI cloning.

### 7. Memory and context parity

Persistent assistant memory, session continuity, long-term context, task resumption, execution-history awareness, memory-aware orchestration.

### 8. Multi-agent coordination parity

Delegation, concurrency, routing, task ownership, distributed execution state, agent communication.

### 9. Deployment workflow parity

Autonomous deployments, provisioning, retries, status tracking, cloud integrations, logs, orchestration.

### 10. Channel / messaging parity

Telegram, Slack, web sessions, gateway messaging, persistent routing, multi-channel assistant identity where OpenClaw provides comparable surfaces.

---

## Phase 2 — improvements after parity

Explicitly deferred until parity is verified:

- privacy-first redesigns, advanced PII filtering, novel orchestration architectures
- experimental agent systems, custom safety frameworks, local-first rewrites
- UX redesigns, alternative memory systems, proprietary workflow inventions

These may proceed only after **AethOS behaviorally matches OpenClaw** for Phase 1 checkpoints.

---

## Forbidden early divergence

Do **not**: redesign core orchestration prematurely; replace workflows before parity; invent alternative UX before parity; optimize architecture before parity; create incompatible abstractions; break workflow equivalence.

---

## Required engineering rule (every PR)

1. What OpenClaw behavior does this reproduce?
2. Does this move AethOS closer to functional parity?
3. What parity category does this improve?

If no parity category applies: **defer** or mark **Phase 2**.

---

## Required test strategy

Maintain parity-oriented tests under `tests/`, including (expand as behaviors land):

| Module | Focus |
| --- | --- |
| `tests/test_openclaw_cli_parity.py` | CLI commands and workflow surfaces |
| `tests/test_openclaw_gateway_parity.py` | Gateway routing and persistence semantics |
| `tests/test_openclaw_workspace_parity.py` | Paths, persistence, workspace state |
| `tests/test_openclaw_agent_parity.py` | Orchestration and agent lifecycle |
| `tests/test_openclaw_memory_parity.py` | Memory and context |
| `tests/test_openclaw_tool_parity.py` | Tools and host execution |
| `tests/test_openclaw_deployment_parity.py` | Deploy flows |
| `tests/test_openclaw_channel_parity.py` | Channels and routing |
| `tests/test_openclaw_runtime_persistence.py` | `~/.aethos/aethos.json` round-trip |
| `tests/test_openclaw_gateway_recovery.py` | Stale gateway PID recovery |
| `tests/test_openclaw_session_recovery.py` | Session rows in runtime JSON |
| `tests/test_openclaw_workspace_persistence.py` | `~/.aethos/workspace` layout |
| `tests/test_openclaw_runtime_registry.py` | Runtime snapshot / registry |
| `tests/test_openclaw_heartbeat.py` | Gateway heartbeat persistence |
| `tests/test_openclaw_long_running_tasks.py` | Execution queue / task shell fields |
| `tests/test_openclaw_task_registry.py` | Persistent task registry + states |
| `tests/test_openclaw_task_checkpointing.py` | Execution checkpoints in `aethos.json` |
| `tests/test_openclaw_scheduler.py` | Background scheduler tick + dispatch |
| `tests/test_openclaw_queue_recovery.py` | Queue + boot recovery + orphan prune |
| `tests/test_openclaw_agent_runtime.py` | Agent rows + task binding persistence |
| `tests/test_openclaw_orchestration_recovery.py` | Interrupted tasks → `recovering` + requeue |
| `tests/test_openclaw_deployment_recovery.py` | Deployment task checkpoint + `deployments` list |
| `tests/test_openclaw_runtime_dispatcher.py` | Recovery queue precedence over execution queue |
| `tests/test_openclaw_execution_plans.py` | Persistent execution plans + dependency shape |
| `tests/test_openclaw_execution_chains.py` | Linear execution chains + cursor |
| `tests/test_openclaw_execution_retry.py` | Retry metadata + exponential backoff |
| `tests/test_openclaw_execution_recovery.py` | Boot continuation for interrupted steps |
| `tests/test_openclaw_execution_dependencies.py` | DAG validation + blocked → ready ordering |
| `tests/test_openclaw_execution_checkpointing.py` | `execution.checkpoints` persistence |
| `tests/test_openclaw_execution_supervisor.py` | Supervisor multi-step completion |
| `tests/test_openclaw_autonomous_execution.py` | Dispatcher re-queue autonomous continuation |

Verify **behavior, workflows, outputs, orchestration, execution semantics** — not branding.

---

## Required documentation alignment

Keep these aligned with this directive and with code:

- `README.md`
- `PROJECT_HANDOFF.md`
- `docs/OPENCLAW_PARITY_AUDIT.md`
- `CONTRIBUTING.md`
- `docs/development/contributing.md`
- **This file** — `docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md`

---

## Current priority order

1. **CLI + gateway parity** — `onboard`, `gateway`, `message send`, daemon lifecycle, gateway state, session routing, workspace persistence.
2. **Autonomous agent parity** — loops, autonomous execution, multi-agent coordination, continuation, memory-aware routing.
3. **Tooling and deployment parity** — deploy orchestration, shell/workspace/env, execution persistence.
4. **Operator UX parity** — Mission Control operational parity, live orchestration visibility, execution and memory inspection, deployment dashboards.

---

## Implementation status

Persistent runtime parity progress (`app/runtime/`, `~/.aethos/aethos.json`, heartbeat, recovery): [OPENCLAW_FUNCTIONAL_PARITY_STATUS.md](OPENCLAW_FUNCTIONAL_PARITY_STATUS.md).

## Phase 2 transition gate (post Phase 1 freeze)

Phase 2 privacy, PII filtering, local-first isolation, and novelty architecture **must not** start as default product work until:

- `tests/soak/`, `tests/edge_cases/`, and `tests/production_like/` pass under `NEXA_PYTEST=1` (see [OPENCLAW_FINAL_PARITY_AUDIT.md](OPENCLAW_FINAL_PARITY_AUDIT.md) for the authoritative verification matrix).
- Repeated-cycle targets (minimum **100** per dimension in default CI via `tests/parity_freeze_gate.py`) and boundedness certification remain green.
- Mission Control orchestration snapshots and `aethos status` / `aethos doctor` remain sufficient for operational triage without raw JSON.

After certification, Phase 2 work listed in the final audit may proceed **without** changing Phase 1 default runtime semantics unless required for security.

Canonical certification record (suite totals, boundedness metrics, Phase 2 readiness): [OPENCLAW_FINAL_PARITY_AUDIT.md](OPENCLAW_FINAL_PARITY_AUDIT.md) — *Phase 1 final operational certification (closure)*.

---

## Final directive

AethOS is not imitating OpenClaw **branding**. AethOS is achieving the same **operational capability**, **workflows**, **orchestration power**, **autonomous execution behavior**, and **operator outcomes** as OpenClaw. **Branding remains AethOS.** **Functionality** must reach OpenClaw parity first. **Everything else is Phase 2.**

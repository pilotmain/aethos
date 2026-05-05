# Agent orchestration (Week 4) — architecture spec

This document is the **implementation-aligned** architecture for making **AethOS** act as a **primary agent** that can register and coordinate **domain-scoped sub-agents**, without replacing existing operator, execution-loop, mission, or host-executor flows.

**Scope control:** “Loose approval” is **explicitly opt-in** via configuration and must remain **auditable**. It is **not** the default in production.

**Related:** `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` (operator vs host executor vs gateway).

---

## 1. Goals

| Goal | Notes |
|------|--------|
| Primary agent | User-facing orchestrator remains **AethOS** (gateway + LLM + existing tools). |
| Sub-agents | Named, domain-tagged **logical agents** that route work and surface status — not separate OS processes by default. |
| Reuse execution | Git / Vercel / tests must call **existing** allowlisted paths: `host_executor.execute_payload`, NL→chain, `local_tool` jobs, operator runners — not new arbitrary shells. |
| Safe rollout | Feature **off** by default; in-process registry acceptable only where documented; production needs **durable** state. |

---

## 2. Core concepts

| Concept | Description |
|---------|-------------|
| **Primary agent** | `NexaGateway` + response stack; user always talks to Nexa first unless a sub-agent turn is explicitly selected. |
| **Sub-agent** | A **handle** (id, name, **domain**, status, **parent scope** = user + channel/session) used for routing and UX (“@git-agent …”). |
| **Mission** (optional later) | A structured multi-step goal; can be **assigned** to a sub-agent record without implying a second LLM unless you add one. |
| **Agent registry** | Stores agent lifecycle: create, list, terminate. |

Domains in v1 should stay aligned with **existing** automation surfaces:

| Domain | Intended mapping (reuse, don’t reinvent) |
|--------|-------------------------------------------|
| `git` | Host executor / NL→chain (`host_executor_nl_chain`), permissions, jobs |
| `vercel` | Allowlisted `host_action` values (e.g. `vercel_projects_list`, `vercel_remove`) — **no** fictional `vercel_deploy` unless implemented as a real allowlisted action |
| `railway` | Operator / execution-loop / Railway runners already in repo |
| `test` | Allowlisted `run_command` / pytest paths via host executor |

---

## 3. High-level flow

```text
User message
    │
    ▼
NexaGateway.handle_message (sync)
    │
    ├─ [optional] Agent orchestration router (flag-gated)
    │       └─ spawn / list / terminate / @mention → structured {"mode":"chat","text":...}
    │
    ├─ Operator execution (existing)
    ├─ External execution loop (existing)
    ├─ Structured routes (missions, dev, …)
    ├─ Approval routes
    └─ Full chat (LLM)
```

Sub-agents **do not** replace the gateway; they **narrow or label** intent before existing pipelines run.

---

## 4. Integration point (gateway)

**File:** `app/services/gateway/runtime.py`, inner `_route` in `handle_message`, **after** credential handling and **before** context snapshot / `try_operator_execution`. Implemented via **`try_sub_agent_gateway_turn`** in `app/services/sub_agent_router.py` (Phase 2).

**Contract:** Orchestration must return the same shape as other early exits:

```python
{"mode": "chat", "text": str, ...optional telemetry keys...}
```

**Sync only:** `NexaGateway.handle_message` is synchronous. Do **not** introduce `async def route` unless the gateway is deliberately refactored for async (out of scope for Week 4 v1).

---

## 5. Implementation phases (recommended)

### Phase 1 — Registry + flag + tests (2–3 days)

**Naming:** `app/services/agent_registry.py` already holds the platform agent catalog (`DEFAULT_AGENTS`, `resolve_mention_key`). Week 4 orchestration lives in **`app/services/sub_agent_registry.py`** (`AgentRegistry`, `SubAgent`, …).

| Deliverable | Detail |
|-------------|--------|
| `app/services/sub_agent_registry.py` | CRUD for orchestration `SubAgent` records; **no** Telegram sends inside registry (avoid circular imports). |
| `nexa_agent_orchestration_enabled` | `Settings` + `.env.example`; default **false**. |
| Unit tests | Spawn, list by scope, terminate, duplicate-name rules. |
| Persistence | **v1:** in-process dict is OK for **single-worker dev** only; document that **multi-worker / multiple API replicas** need DB/Redis. |

**Phase 26 — Mission Control (user-facing names):** `app/services/team/` adds `TeamRoster`, `TeamMember`, `roles`, and `skills` — product language (*team members*, *roles*, *skills*) over the same `AgentRegistry` / `SubAgent` records; no change to spawn/execute semantics.

**Singleton:** A process-wide singleton is fine for dev; for production, prefer **stateless service + DB table** or explicit “orchestration only on one worker” (documented).

### Phase 2 — Router + gateway hook (2–3 days) ✅

| Deliverable | Detail |
|-------------|--------|
| `app/services/sub_agent_router.py` | **Sync** `AgentRouter.route(text, chat_id)`; `orchestration_chat_key(gctx)`; `try_sub_agent_gateway_turn(gctx, text) -> dict \| None`. |
| `NexaGateway.handle_message` | After external-credential handling, before operator execution: call `try_sub_agent_gateway_turn`. Gated by `nexa_agent_orchestration_enabled`. |
| UX (this phase) | **Leading** `@<name> [message]` only. No spawn/list natural language in the router yet. |
| Execution | Router **does not** run host tools in Phase 2; Phase 3 enqueues / executes. |

### Phase 3 — Execution + optional in-process run ✅

| Deliverable | Detail |
|-------------|--------|
| `app/services/sub_agent_executor.py` | Sync `AgentExecutor`: git (NL→chain, `git_status`), vercel (`vercel_projects_list`), test (`run_command` pytest), railway (placeholder string). |
| `nexa_agent_orchestration_autoqueue` | Default **false**: enqueue `host-executor` jobs via `enqueue_host_job_from_validated_payload`. When **true**, calls `execute_payload` in-process — audit `nexa_event=sub_agent_autoqueue` (**dev / trusted hosts only**). |
| Gateway | `try_sub_agent_gateway_turn(..., db)` passes DB + `user_id` into routing; non-empty text after `@agent` runs the executor. Empty mention body → readiness hint only. |

### Phase 3b — Policy hardening (later)

**Not** a silent bypass of `needs_approval` in generic host code — only the orchestration autoqueue path.

| Approach | Rationale |
|----------|-----------|
| Keep autoqueue **default off** | Production should enqueue + approve. |
| Audit | `nexa_event=sub_agent_autoqueue` and queued `sub_agent_queued` logs include domain / job id. |

### Phase 4 — Channel commands (optional)

Telegram slash commands should live in **`app/bot/telegram_bot.py`** (or the command table there), not in `external_execution_session.py` unless that file is already the command router (verify before editing).

### Phase 5 — Hardening (Week 5) ✅

| Area | Implementation |
|------|----------------|
| **Audit** | `app/services/sub_agent_audit.py` — `log_agent_event(...)` with `nexa_event=agent_audit`, `agent_audit_event`, stable fields. Spawn/terminate also emit audit lines from `sub_agent_registry`. Auto-queue path logs `autoqueue_execute`, `autoqueue_redirect_queue`. |
| **Rate limits** | `app/services/sub_agent_rate_limit.py` — in-memory rolling window per **agent**, **chat**, **domain** (single worker). Check **before** work; **record** only after a successful dispatch. Settings: `nexa_agent_rate_limit_*`, `nexa_agent_rate_limit_window_seconds`. |
| **Auto-queue policy** | `app/services/sub_agent_autoqueue_guard.py` — when `nexa_agent_orchestration_autoqueue` is on: optional chat allowlist (empty = all chats), domain allowlist (default `git` in config — set explicitly for other domains), and optional cap on successful in-process runs per agent (`nexa_agent_autoqueue_require_approval_after`). On deny, executor falls back to the normal approval **queue** when `db` + `user_id` exist. |
| **Idle timeout** | `AgentRegistry.cleanup_idle_agents()` uses `nexa_agent_idle_timeout_seconds`. `try_sub_agent_gateway_turn` calls throttled cleanup (`nexa_agent_cleanup_interval_seconds`) so stale IDLE agents are removed without a separate cron. |
| **Max agents per chat** | Enforced in `AgentRegistry.spawn_agent` via `nexa_agent_max_per_chat` (duplicate name in chat also blocked). |

**Not in scope for Week 5:** full RBAC, persistent audit DB, distributed (Redis) rate limiting.

---

## 6. Spec corrections (pasted draft vs this repo)

| Draft assumption | Actual |
|------------------|--------|
| `execute_payload` → dict with `success` / `error` | Returns **`str`**. Success/failure for chains uses text heuristics + `ValueError` for validation. |
| `host_action: vercel_deploy` | **Not** an allowlisted action unless added to `host_executor` with real argv. |
| `from .cli_backends import get_cli_command` | **Not** in this spec; do not add without verifying the module exists. |
| Async `AgentRouter.route` | Gateway is **sync**; use sync router or run async in a thread only with a deliberate design. |
| In-memory registry in production | **Unreliable** with multiple Uvicorn workers; scope to dev or add storage. |

---

## 7. Environment variables (proposed)

| Variable | Purpose |
|----------|---------|
| `NEXA_AGENT_ORCHESTRATION_ENABLED` | Master switch for registry + router hook. |
| `NEXA_LOOSE_APPROVAL_MODE` or more specific name | If present, **tighten** to one behavior (e.g. auto-queue only specific chain templates) before merge. |

Host executor flags stay as today (`NEXA_HOST_EXECUTOR_ENABLED`, chain, NL→chain, etc.).

---

## 8. Success criteria (Week 4)

- [ ] With orchestration **on**, “create a git agent” creates a sub-agent record scoped to the user + session.
- [ ] “list agents” returns active agents for that scope.
- [ ] “@git-agent …” can be recognized and either (a) formats a reply that points to existing host/chain flow, or (b) enqueues the same jobs as today — **no** new unapproved shell.
- [ ] Terminate marks agent **terminated** and removes it from list.
- [ ] With orchestration **off**, zero behavior change.
- [ ] Tests cover registry + router determinism; no flakiness from global singleton in parallel tests (use module-scoped reset or non-singleton factory in tests).

---

## 9. Risk register

| Risk | Mitigation |
|------|------------|
| Spawning unlimited agents | Cap per user + TTL. |
| “Loose approval” opens host mutations | Narrow scope, audit logs, default off. |
| Split-brain registry across workers | Document dev-only; DB for prod. |
| Duplicating gateway logic | Router delegates to existing host/operator paths. |

---

## 10. Deliverables checklist

| Item | Status |
|------|--------|
| `docs/AGENT_ORCHESTRATION.md` (this file) | ✅ |
| `app/services/sub_agent_registry.py` | ✅ Phase 1 |
| `app/services/sub_agent_router.py` | ✅ Phase 2 |
| Gateway hook in `NexaGateway.handle_message` | ✅ Phase 2 |
| Settings + `.env.example` | ✅ Phase 1 (router in Phase 2) |
| Unit tests (`tests/test_agent_registry.py`, `tests/test_sub_agent_router.py`) | ✅ Phase 1–2 |
| `nexa_agent_orchestration_autoqueue` + executor | ✅ Phase 3 |
| Policy tightening for autoqueue | ✅ Week 5 (`sub_agent_autoqueue_guard` + rate limits + audit) |

---

## 11. Next step

Reply in chat with one of:

- **“implement Week 4 Phase 1”** — registry + settings + tests + `.env.example` only  
- **“implement Week 4”** — phased PRs in order (1 → 2 → 3)  
- **“modify spec: …”** — iterate this document before code  

---

## 12. Phase 16a — bounded delegation (`agent_team`)

This phase is **separate** from Week 4 sub-agent registry routing (`sub_agent_router`). It reuses **`create_assignment`** / **`dispatch_assignment`** to fan out one user goal to **multiple custom-agent handles** with a shared **`spawn_group_id`** and orchestration metadata in **`input_json`**.

### Feature flags (environment)

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXA_ORCHESTRATION_ENABLED` | `false` | When true, gateway recognizes `/delegate …` and creates assignments. |
| `NEXA_ORCHESTRATION_MAX_DELEGATES` | `5` | Max distinct `@handles` per delegation (hard-clamped in policy). |
| `NEXA_ORCH_MAX_PARALLEL_AGENTS` | `3` | Max concurrent `dispatch_assignment` threads when `parallel` is used. |
| `NEXA_ORCH_DELEGATION_TIMEOUT_MS` | `30000` | Per-dispatch timeout budget (parallel path uses seconds derived from this). |
| `NEXA_ORCH_REQUIRE_APPROVAL` | `false` | When true, assignments are created as **`waiting_approval`** and not dispatched. |

### Gateway usage

Send a message beginning with **`/delegate`** (so accidental `@mentions` do not trigger orchestration):

```text
/delegate @agent-one @agent-two Summarize the repo and open a PR draft
/delegate parallel @frontend @backend Ship the hotfix with coordinated checks
```

Handles must match **`@handle`** tokens at the start of the command; the rest is the **goal** text. At least **two** distinct agents are required.

### REST API

Mission Control auth only (**not** cron Bearer): **`X-User-Id`** plus optional **`Authorization: Bearer`** when `NEXA_WEB_API_TOKEN` is set.

- **`POST /api/v1/orchestration/delegate`**

```json
{
  "agents": ["agent-one", "agent-two"],
  "goal": "Your shared objective",
  "parallel": false
}
```

Response mirrors **`run_delegation`**: `ok`, `spawn_group_id`, `assignment_ids`, `results`, etc.

### SQLite and parallel dispatch

Parallel dispatches run **`dispatch_assignment`** in a **`ThreadPoolExecutor`**. Each worker opens its **own** SQLAlchemy session (`SessionLocal`) so SQLite connections are not shared across threads.

### Logs

Delegation emits structured logs with **`nexa_event`: `orchestration_delegate`** (see `app/services/orchestration/delegate.py`).

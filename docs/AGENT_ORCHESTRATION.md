# Agent orchestration (Week 4) — architecture spec

This document is the **implementation-aligned** architecture for making Nexa act as a **primary agent** that can register and coordinate **domain-scoped sub-agents**, without replacing existing operator, execution-loop, mission, or host-executor flows.

**Scope control:** “Loose approval” is **explicitly opt-in** via configuration and must remain **auditable**. It is **not** the default in production.

**Related:** `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` (operator vs host executor vs gateway).

---

## 1. Goals

| Goal | Notes |
|------|--------|
| Primary agent | User-facing orchestrator remains **Nexa** (gateway + LLM + existing tools). |
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

**File:** `app/services/gateway/runtime.py`, inner `_route` in `handle_message`, **after** credential handling and **before** `try_operator_execution`.

**Contract:** Orchestration must return the same shape as other early exits:

```python
{"mode": "chat", "text": str, ...optional telemetry keys...}
```

**Sync only:** `NexaGateway.handle_message` is synchronous. Do **not** introduce `async def route` unless the gateway is deliberately refactored for async (out of scope for Week 4 v1).

---

## 5. Implementation phases (recommended)

### Phase 1 — Registry + flag + tests (2–3 days)

| Deliverable | Detail |
|-------------|--------|
| `app/services/agent_registry.py` | CRUD for `SubAgent` records; **no** Telegram sends inside registry (avoid circular imports). |
| `nexa_agent_orchestration_enabled` | `Settings` + `.env.example`; default **false**. |
| Unit tests | Spawn, list by scope, terminate, duplicate-name rules. |
| Persistence | **v1:** in-process dict is OK for **single-worker dev** only; document that **multi-worker / multiple API replicas** need DB/Redis. |

**Singleton:** A process-wide singleton is fine for dev; for production, prefer **stateless service + DB table** or explicit “orchestration only on one worker” (documented).

### Phase 2 — Router (2–3 days)

| Deliverable | Detail |
|-------------|--------|
| `app/services/agent_router.py` | **Sync** `try_route(gctx, text, db) -> dict \| None`. |
| UX | Phrases: “create a git agent”, “list agents”, “terminate agent …”, `@<name> <message>`. |
| Execution | Router **does not** call `execute_payload` and treat the return as a dict. Today `execute_payload` returns a **string** (user-facing text). Host mutations that need approval should go through **`host_executor_chat` / `AgentJobService`** like the rest of the product. |

### Phase 3 — “Loose approval” (explicit, auditable)

**Not** a silent bypass of `needs_approval` in generic code.

| Approach | Rationale |
|----------|-----------|
| **Do not** add `if loose: return True` inside permission checks without scope | Collapses security for all host actions. |
| Prefer | Separate, **narrow** path: e.g. auto-queue as `queued` only for **pre-validated** chain templates + audit log line; or a dedicated “dev only” flag with **max** steps and **repo** allowlist. |

If Week 4 ships “loose” behavior, it must be:

- `NEXA_LOOSE_APPROVAL_MODE` (or better: `NEXA_AGENT_ORCHESTRATION_AUTOQUEUE=1`) **default false**
- Log every auto-queued job with `nexa_event` and **user_id**
- Documented in this file and in `WEEK2_HOST_ACTION_CHAINS.md` if it touches host jobs

### Phase 4 — Channel commands (optional)

Telegram slash commands should live in **`app/bot/telegram_bot.py`** (or the command table there), not in `external_execution_session.py` unless that file is already the command router (verify before editing).

### Phase 5 — Hardening (Week 5+)

- Max agents per user/chat, rate limits, idle TTL
- Durable registry
- Remove or tighten loose mode; policy / allowlist per repo

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
| `app/services/agent_registry.py` | Phase 1 |
| `app/services/agent_router.py` | Phase 2 |
| Gateway hook in `NexaGateway.handle_message` | Phase 2 |
| Settings + `.env.example` | Phase 1–2 |
| Unit tests | Phase 1+ |
| Loose mode (if any) behind flag + audit | Phase 3 |

---

## 11. Next step

Reply in chat with one of:

- **“implement Week 4 Phase 1”** — registry + settings + tests + `.env.example` only  
- **“implement Week 4”** — phased PRs in order (1 → 2 → 3)  
- **“modify spec: …”** — iterate this document before code  

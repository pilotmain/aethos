# Nexa: project handoff (Cursor & agents)

This file is the **architecture and direction** home for future work. Product onboarding stays in the root [README.md](../README.md). **Practical “run, test, queue more work” onboarding:** [DEVELOPMENT_HANDOFF.md](./DEVELOPMENT_HANDOFF.md).

**Single path for “finish this in the repo” / Cursor-style work:** queue a **`dev_executor` agent job** (Telegram: `/dev create-cursor-task …`, `/dev prepare-fix …`, `/improve …`, or natural “tell Cursor to…”). The worker is [`scripts/dev_agent_executor.py`](../scripts/dev_agent_executor.py) and writes **`dev_job_{id}.md`** plus handoff markers for Codex — not a separate manual-only `cursor_task_*.md` flow. The root `CURSOR_PROJECT_HANDOFF.md` is a **stub** pointing here only; do not author long handoffs in the repo root.

---

## What this project already is

- **FastAPI** backend with **SQLite** default storage and automatic schema creation.
- **Telegram bot** frontend for conversational task capture and follow-up.
- **Brain-dump → task extraction → daily-plan** pipeline.
- **Check-in scheduler** plus **polling worker** for follow-up prompts.
- **Safety-hardening** for external LLM calls via [`app/services/safe_llm_gateway.py`](../app/services/safe_llm_gateway.py).
- **Local developer automation** through `/dev`, [`LocalAction`](../app/models/local_action.py) + [`DevTask`](../app/models/dev_task.py) queues, and workers under [`scripts/`](../scripts).

---

## Core architecture

| Area | Location |
|------|----------|
| API entry | [`app/main.py`](../app/main.py) |
| Telegram bot | [`app/bot/telegram_bot.py`](../app/bot/telegram_bot.py) |
| Orchestration | [`app/services/orchestrator_service.py`](../app/services/orchestrator_service.py) |
| Memory service | [`app/services/memory_service.py`](../app/services/memory_service.py) |
| Safety gateway | [`app/services/safe_llm_gateway.py`](../app/services/safe_llm_gateway.py) |
| Planner / composer | [`app/services/planner_service.py`](../app/services/planner_service.py), [`app/services/response_composer.py`](../app/services/response_composer.py) |
| Local dev / agent | [`scripts/dev_agent_executor.py`](../scripts/dev_agent_executor.py), [`scripts/local_tool_worker.py`](../scripts/local_tool_worker.py) |

---

## What was added: agent memory and API

- **Real agent memory** state, not preferences-only.
- **Product concepts** at repo root: [`soul.md`](../soul.md), [`memory.md`](../memory.md).
- **API memory** routes (see OpenAPI at `/docs` for the exact list): e.g. state, remember, forget, soul.
- **Telegram** natural-language memory: `remember …`, `forget …`, `soul: …`, etc.
- **Forgetting** removes matching open work where implemented (e.g. tasks / check-ins) so “stop nagging me about that report” is consistent.

---

## Current product shape

The app sits between a **personal productivity bot** and a **locally controlled assistant platform**. Strength: core logic, memory, safety gateway, and worker scripts are **local and inspectable**. Gaps: no full **multi-agent runtime**, no **retrieval-ranked** memory with conflict policies, no **unified approval center** for risky operations, no rich **user-visible audit log** for every decision, and **Telegram** remains the main surface (no full operator dashboard yet).

---

## Biggest current gaps (strategic)

1. No first-class **multi-agent coordination** model.
2. Memory is real but still **lightweight** vs retrieval, conflicts, and expiry policy.
3. No **unified action approval** for higher-risk local or external actions.
4. No **audit / explain-why** trail across memory, plans, and schedules.
5. No **benchmark harness** against strong open-source agent patterns.

---

## Best-in-class direction (north star)

- **Agent supervisor** with shared goals: planner, research, executor, critic (names flexible).
- **Shared workspace memory**: `soul.md`, `memory.md`, `scratchpad.md` for humans; **structured DB** for search, expiry, provenance, delete.
- **Multi-agent patterns**: one shared plan object, ownership per sub-task, **merge/review checkpoints** before execution.
- **OpenClaw / OpenCode–class strengths** without giving up control: local-first, **allowlisted tools**, **approval gates** (browser, FS, shell, external APIs), **replayable logs**, **policy sandboxing**.
- **Memory hygiene**: TTL, pin/unpin, override conflicts, “why do you remember this?”.
- **Operator UX** (when ready): memory viewer, queued actions, follow-up queue, model toggle, **safety / redaction audit** panel.

---

## Concrete build order (suggested)

1. **Structured memory types** (rule, preference, project, person, do_not_remind, session_fact).
2. **Memory ranking** so prompt context = most relevant *active* items.
3. **Explicit deletion** by key and by semantic match from a UI.
4. **Supervisor runtime** with delegation and completion criteria.
5. **Human approval checkpoints** for any local action beyond read-only inspection.
6. **Internal dashboard** for plans, memory, check-ins, queued jobs.
7. **Evaluation** scenarios: correctness, forgetting, safety, trust.

---

## Guardrails (do not drop these)

1. **Single provider / tool boundary**  
   Keep [`safe_llm_gateway`](../app/services/safe_llm_gateway.py) as the choke point for *external* model calls, and **extend it toward a policy engine** (allowlist, reason codes, optional human approval) as you add tools—not parallel ad-hoc client calls from feature code.

2. **Forget = no stale nags everywhere**  
   Any new scheduler, reminder, or follow-up must respect the same contract as current forget/cleanup: **if the user has removed a concern from memory, do not keep optimizing or nudging in parallel** without an explicit, logged exception path.

3. **Unify jobs before a supervisor**  
   Treat [`dev_tasks`](../app/models/dev_task.py) and [local actions](../app/models/local_action.py) as the **seed of one cancellable, loggable job model** (shared status lifecycle, `result` / `error`, idempotency rules). **Then** add a supervisor that dispatches *jobs*, not ad-hoc scripts.

---

## Next implementation sketch: unified job model → supervisor

**Goal:** one internal abstraction for “work the user (or agent) queued from Telegram or API,” with a **stable lifecycle** and **auditability**.

- **Job kind**: `dev_task` | `local_action` | (future) `agent_run` | `tool_invocation` — or a single table with a `type` / `source` field if you merge implementations later.
- **Common fields (conceptual):** `id`, `user_id`, `status` (`queued` / `in_progress` / `waiting` / `completed` / `failed` / `cancelled` / `blocked`), `created_at` / `updated_at`, `payload` (JSON or structured columns), `result` / `error_message`, `correlation_id` for log tracing.
- **Worker contract:** pick `queued` → validate **allowlisted** `command` or `action_type` → run → persist result; **never** `shell=True` on user text.
- **Cancellation:** `status=cancelled` or soft-delete; workers must check status **before** heavy steps and at safe yields.
- **Supervisor (later):** enqueues **jobs**, assigns to agent roles, gates risky steps — but **jobs** remain the durable record.

This keeps the current scripts as **one implementation** of the worker, not the model of record.

---

## Suggested implementation notes (repo-specific)

- Preserve **local-first / safe-first** posture.
- Treat **memory deletion** as a product feature, not a side effect.
- Unify **reminders and memory** so a user’s “stop reminding me / forget that” is reflected in **both** the memory store **and** scheduled nudges, with no silent split-brain.
- If you add **multi-agent** flows, make every action **attributable, cancelable, and reviewable**; add a **durable event log** (remember / forget / schedule / job state).

---

## Summary

This repo already has a strong base: planning, follow-ups, memory, Telegram, and safety. The highest-leverage next move is a **supervised local agent platform**: shared memory, explainable actions, and **multi-agent collaboration under user control** — built on a **unified job model** and the guardrails above.

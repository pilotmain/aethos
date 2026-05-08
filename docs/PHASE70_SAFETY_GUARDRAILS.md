# Phase 70 — Safety & Cost Guardrails (UI approvals, cost-aware router, host_executor dry-run)

Phase 70 ships three independently useful capabilities behind feature flags so
existing flows are untouched until each call site is migrated:

1. **Mission Control "Pending Approvals" panel** — UI surface over the existing
   `agent_jobs.awaiting_approval` queue (Phase 38). No new approvals table.
2. **Opt-in `cost_aware_router`** — thin helper layered on
   `app/services/llm_costs.py` + `app/services/llm/registry.py`. No automatic
   model swaps until each call site opts in.
3. **`host_executor.execute_payload(simulate=True)` dry-run mode** — runs the
   real validation + permission pipeline but returns a planned-actions summary
   instead of executing. Off by default.

## Why this differs from the proposed spec

The original spec drafted a parallel `approval_requests` table, a parallel
`MODEL_COSTS` map, and a custom `useAuth` web client. Auditing the codebase
showed those facilities **already exist** with deeper integration than the
draft (Telegram approvals, Mission Control jobs UI, BYOK pricing). Building
parallel surfaces would have:

- split the source of truth between two approval queues,
- duplicated and divergence-prone pricing data,
- bypassed the standardized `webFetch` + `readConfig` web client adopted in
  Phase 67/68, and
- bypassed Phase 30/31/32/48 lockdown scanners (no `/jobs` literal in web
  sources outside `/web/jobs`).

The Phase 70 implementation reuses the existing primitives instead.

## What landed

### 1. Approvals UI

| File | Change |
|---|---|
| `app/api/routes/approvals.py` | New router. `GET /api/v1/approvals/pending` returns the caller's `agent_jobs.awaiting_approval=True` rows with a sanitized payload preview. `GET /api/v1/approvals/risk-preview?text=…` wraps `assess_interaction_risk`. Read-only by design. |
| `app/main.py` | Includes the new router. |
| `app/api/routes/web.py` | New `POST /api/v1/web/jobs/{id}/cancel` proxy so the UI can cancel a pending job from the same auth surface as `/web/jobs/{id}/decision`. |
| `web/lib/api/approvals.ts` | Typed client (`fetchPendingApprovals`, `decideJob`, `cancelJob`) using `webFetch` and the `/web/jobs/...` proxies. |
| `web/app/mission-control/(shell)/approvals/page.tsx` | New page: lists each pending approval, exposes Approve / Deny / Cancel job, sanitized payload preview. |
| `web/lib/navigation.ts` | New "Approvals" nav item between Budget and Advanced. |

### 2. Cost-aware model selection (opt-in helper)

| File | Change |
|---|---|
| `app/services/llm/cost_aware_router.py` | New module: `select_model_for_task`, `estimate_token_count`, `estimate_messages_cost` (delegates to `llm_costs.estimate_llm_cost`), `recommend_cheaper_model_if_over_budget`, `route_for_task` returning a `CostAwareDecision`. No call sites are changed. Wraps the existing pricing table — no parallel cost map. |

The router is a building block; per-call-site adoption (`sub_agent_executor`,
`intent_classifier`, etc.) is a follow-up so behavior change rolls out
incrementally with telemetry.

### 3. `host_executor` dry-run

| File | Change |
|---|---|
| `app/services/host_executor.py` | New `simulate: bool \| None = None` kwarg on `execute_payload`. When `True` (or when `nexa_host_executor_dry_run_default=True`), runs validation + permission enforcement and then returns a per-action `[SIMULATED]` plan instead of executing. New `_format_simulation_plan` covers `git_status`, `git_push`, `run_command`, `file_read`, `file_write`, `list_directory`, `find_files`, `read_multiple_files`, `plugin_skill`, and `chain` (lists each inner step). |

### Settings + env

Added to `app/core/config.py` and synced to `.env.example` + `.env`:

| Env var | Default | Purpose |
|---|---|---|
| `NEXA_APPROVALS_PANEL_ENABLED` | `true` | Gate the GET pending endpoint + nav link. |
| `NEXA_COST_AWARE_ENABLED` | `false` | Opt in to cost-aware downgrades from `cost_aware_router`. |
| `NEXA_COST_AWARE_MAX_PER_TASK_USD` | `0.05` | Per-call budget cap for the downgrade rule. |
| `NEXA_COST_AWARE_DEFAULT_PROVIDER` | `anthropic` | Default-tier provider. |
| `NEXA_COST_AWARE_DEFAULT_MODEL` | `claude-sonnet-4-5` | Default-tier model. |
| `NEXA_COST_AWARE_CHEAP_PROVIDER` | `anthropic` | Cheap-tier provider. |
| `NEXA_COST_AWARE_CHEAP_MODEL` | `claude-haiku-4-5` | Cheap-tier model. |
| `NEXA_HOST_EXECUTOR_DRY_RUN_DEFAULT` | `false` | When true, `execute_payload` dry-runs unless callers pass `simulate=False`. |

### Tests

| File | Coverage |
|---|---|
| `tests/test_approvals_api_phase70.py` | Pending list scoped to caller, `payload_preview` strips unknown sensitive keys, settings flag gates the endpoint (503), `risk-preview` round-trips through `assess_interaction_risk`. |
| `tests/test_cost_aware_router_phase70.py` | Token estimator, default-vs-cheap selection, downgrade only when over budget, never downgrades when already on cheap tier or when disabled, `route_for_task` end-to-end. |
| `tests/test_host_executor_simulate_phase70.py` | `simulate=True` returns a plan and skips `_run_argv` / disk writes for `git_status`, `run_command`, `file_write`, and `chain`; settings default flag triggers without explicit kwarg; explicit `simulate=False` overrides; disabled-executor still raises. |

## What is intentionally deferred

- **Per-call-site cost-aware integration.** Wiring `cost_aware_router` into
  `sub_agent_executor` / `intent_classifier` would change real LLM behavior
  and needs its own phase + telemetry. The router is ready to import.
- **Approvals → simulate cross-cut.** The Approvals page does not yet expose
  a "Simulate" button. The host-executor primitive is in place; surface
  wiring is a Phase 70.x follow-up.
- **CEO Dashboard cost metrics.** The dashboard already shows model usage via
  the existing `llm_usage_event` pipeline; Phase 70 adds no new metric.
- **No new `approval_requests` table.** Approvals continue to live on
  `agent_jobs`. If a non-job action ever needs approval, this is the right
  point to add a separate table — but only after a real use case appears.

## Verification

```bash
.venv/bin/python -m compileall -q app
# clean

.venv/bin/python -m pytest tests/test_approvals_api_phase70.py \
    tests/test_cost_aware_router_phase70.py \
    tests/test_host_executor_simulate_phase70.py -q
# 23 passed

.venv/bin/python -m pytest tests/test_host_executor.py \
    tests/test_host_executor_chain.py tests/test_host_executor_chat.py \
    tests/test_host_executor_intent.py tests/test_host_executor_visibility.py -q
# 40 passed (no regressions)

.venv/bin/python -m pytest tests/test_identity_final_phase48.py \
    tests/test_no_legacy_commands_phase31.py \
    tests/test_no_legacy_handlers_phase32.py \
    tests/test_system_identity_locked.py tests/test_ui_clean_phase30.py -q
# 212 passed (lockdown scanners green)

cd web && npx tsc --noEmit
# clean
```

## Manual smoke (local)

1. Open Mission Control → **Approvals**. The panel renders with “Nothing
   waiting on you.” when no jobs are pending.
2. Create a pending job (Telegram approval flow or any code path that sets
   `agent_jobs.awaiting_approval=True`). The panel lists it with kind,
   worker, host_action, target, risk, and a sanitized payload preview.
3. Click **Approve** / **Deny** — both call `/api/v1/web/jobs/{id}/decision`
   (same surface as Telegram). The list refreshes. **Cancel job** calls
   the new `/api/v1/web/jobs/{id}/cancel` proxy.
4. Backend: `python -c "from app.services.host_executor import execute_payload;
   print(execute_payload({'host_action': 'git_status'}, simulate=True))"`
   should print a `[SIMULATED]` plan without running git.

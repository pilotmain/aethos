# Runtime worker operational memory (Phase 3 Step 7)

Runtime workers persist **bounded operational memory** separate from conversational chat history.

## Storage (`aethos.json`)

| Key | Purpose |
|-----|---------|
| `worker_memory` | Per-worker recent tasks, outputs, failures, workspace snippets |
| `worker_deliverables` | Durable deliverables (survive worker expiration) |
| `worker_continuations` | Follow-up / restart recovery links |
| `worker_session_context` | Last active worker per chat scope |

## Deliverable types

`research_summary`, `deployment_report`, `repair_summary`, `verification_report`, `planning_output`, `provider_diagnostic`, `automation_outcome`, `workflow_summary`, `general_output`

## APIs (Step 7–8)

- `GET /api/v1/mission-control/worker-deliverables` — search (`q`, `handle`, `type`, `task_id`, `project_id`, `provider`, `status`, date range)
- `GET /api/v1/mission-control/deliverables` — global deliverable list
- `GET /api/v1/mission-control/deliverables/{id}` — detail
- `GET /api/v1/mission-control/deliverables/{id}/export?format=markdown|text|json`
- `GET /api/v1/mission-control/runtime-workers/{id}` — worker detail
- `GET /api/v1/mission-control/runtime-workers/{id}/deliverables|memory|continuations`
- Runtime truth keys: `worker_memory`, `worker_deliverables`, `worker_continuations`, `worker_effectiveness`

## Env caps (Step 8)

`AETHOS_WORKER_MEMORY_TASK_LIMIT`, `AETHOS_WORKER_MEMORY_OUTPUT_LIMIT`, `AETHOS_WORKER_DELIVERABLE_LIMIT`, `AETHOS_WORKER_CONTINUATION_LIMIT`

## Follow-up queries (no task ID)

Resolved from session + worker memory:

- `what did you find?`
- `show last result`
- `show latest deliverables`
- `show deployment reports`

## Constraints

Memory is capped (~12 recent items per category). Deliverables globally capped at 200 entries. Workers may expire; deliverables and history remain.

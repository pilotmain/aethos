# Phase 67: Auto-dispatch agent assignments + Projects "Agent assignments" panel

## Why this differs from the original spec

Auditing the codebase before applying revealed the spec collided with shipped behavior:

- `web/app/mission-control/(shell)/team/page.tsx` already merges orchestration sub-agents (`fetchOrchestrationAgentsResolved`) **and** governance org members, with org chart, role mapping, and current-task badges. Replacing it with a localStorage-only fetch hard-coded to `tg_*` would drop those features.
- The `Task` model in `app/models/task.py` is the **personal todo** (no `assigned_to` column). Agent work uses `AgentAssignment` (`app/models/agent_team.py`) with `assigned_to_handle` and a full REST API (`/api/v1/agent-assignments`) plus a working `dispatch_assignment` service that handles host tools, approvals, custom user agents, and audit/event emission.
- `web/lib/ws/missionControlStream.ts` is already a single shared MC websocket with reconnect + ping; the spec's new `task_listener.ts` would open a duplicate socket per page.

Phase 67 therefore applies the **intent** (assigning to an agent should run the agent) against the **assignment system**, not the personal todo system.

## Changes

### Backend

| File | Change |
|------|--------|
| `app/schemas/agent_organization.py` | `AgentAssignmentCreate.auto_dispatch: bool \| None = None` |
| `app/api/routes/agent_organization.py` | After successful `POST /agent-assignments`, when `auto_dispatch` resolves to `True`, run `dispatch_assignment(...)` and merge result under `auto_dispatch` in the response. |
| `app/core/config.py` | `nexa_assignment_auto_dispatch_default: bool = True` |
| `.env.example`, `.env` | `NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT=true` |

`dispatch_assignment` is unchanged, so all existing safety paths (host-tools gate, permission/approval, custom-agent presence checks, duplicate-detection 409) still apply.

### Frontend

| File | Change |
|------|--------|
| `web/lib/api/assignments.ts` | New typed client: `fetchAgentAssignments`, `createAgentAssignment` (with `auto_dispatch` flag), `dispatchAgentAssignment`, `cancelAgentAssignment`, plus `groupAssignmentsByAgent` / `summarizeAssignments` helpers. |
| `web/components/mission-control/Projects/AssignmentsByAgentPanel.tsx` | New read-only panel: live counts (Total/Running/Done/Failed) + per-agent group with last 8 titles & status badges. |
| `web/app/mission-control/(shell)/projects/page.tsx` | Render the panel above the existing project list. No nav, route, or layout changes. |
| `web/lib/__tests__/assignments.test.ts` | Vitest coverage for grouping / summary / terminal helpers. |

The Team page, governance flows, mission Kanban, checklist board, and the shared MC websocket are **untouched**.

## Verification

```bash
cd ~/aethos
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest \
    tests/test_agent_assignment_auto_dispatch.py \
    tests/test_response_truth_acceptance.py \
    tests/test_agent_team_market_assignment.py -q
cd web
npm test
```

Then restart the API + Telegram bot and reload `/mission-control/projects`.

## Behavior

- `POST /api/v1/agent-assignments` (no `auto_dispatch` field, default settings):
  - Persists row, runs `dispatch_assignment` immediately, returns `{...assignment, auto_dispatch: { ok, ... } }`.
- `POST /api/v1/agent-assignments` with `"auto_dispatch": false`:
  - Persists row only — caller must `POST /api/v1/agent-assignments/{id}/dispatch` later.
- `NEXA_ASSIGNMENT_AUTO_DISPATCH_DEFAULT=false`:
  - Same as omitting + sending false — restores the legacy two-step.
- Duplicate (recent open assignment with same agent + title): still **409** — auto-dispatch never runs.
- Dispatch raises: persisted row is still returned with `auto_dispatch: { ok: false, error: "dispatch_failed" }` so the client can retry via the explicit dispatch route.

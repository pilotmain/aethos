# Phase 76 — Blue-Green Safety Simulation

Operators can preview **what the host executor would do** before approving real work. Simulation reuses `execute_payload(..., simulate=True)` (Phase 70) so validation and permission gates match a real run.

## Configuration

| Env | Purpose |
|-----|---------|
| `NEXA_SIMULATION_ENABLED` | Master switch for simulation HTTP endpoints and Telegram previews (default on). |
| `NEXA_SIMULATION_SANDBOX_MODE` | When true (default), `git_commit` simulations run `git status --short` under the exec root for a changed-files list. When false, that probe is skipped. |
| `NEXA_SIMULATION_MAX_DIFF_LINES` | Caps unified diff lines for `file_write` previews (default 500). |

Application settings live on `Settings` in `app/core/config.py`.

## HTTP API

- `GET|POST /api/v1/approvals/{job_id}/simulate` — Owner role only; pending job must belong to the caller and `awaiting_approval=true`. Returns `{ ok, plan_text, structured_plan, error, … }`. Persists the snapshot on `agent_jobs.simulation_result` for audit.
- `POST /api/v1/approvals/-/simulate-payload` — Same preview for an arbitrary payload body (Mission Control / tooling).
- `GET /api/v1/approvals/-/capabilities` — Flags for the UI (`simulation_enabled`, `max_diff_lines`, `is_owner`, …).

Approve / deny remains `POST /api/v1/web/jobs/{id}/decision`.

## Telegram

1. **`/simulate <jobId>`** — Preview a pending approval; inline **Approve & Execute** uses the same path as `/approve`.
2. **Plain message** starting with `/simulate ` — Strips the prefix and runs the deterministic NL → host payload path in **simulate-only** mode (no queue). Shows a preview and **Approve & Execute** (`simtxt:exec`) to send the **stripped** line through the normal confirmation / queue flow.

## Web UI

Mission Control → **Pending approvals**: **Simulate** opens a modal with plan text and a visual diff (`DiffViewer`) when `structured_plan.diff.unified` is present. **Approve & Execute** calls the existing decision proxy.

## Implementation Notes

- Structured previews: `build_simulation_plan()` in `app/services/host_executor.py`.
- Pending NL execution text is stored on `conversation_contexts.simulate_execute_pending_json` until the operator confirms.

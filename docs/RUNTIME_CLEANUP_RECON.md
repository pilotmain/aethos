# Runtime cleanup reconnaissance (Phase 2 Step 10)

Preparation for a future full cleanup phase. **Do not delete** without parity verification.

## Duplicate payload builders (consolidate → `runtime_truth.py`)

| Location | Notes |
|----------|--------|
| `runtime_intelligence.py` | Now delegates to `runtime_truth` |
| `runtime_panels.py` | Now delegates to `runtime_truth` |
| `nexa_next_state.py` | Still builds `orchestration_runtime` + inline `runtime_health` — keep for `/state` parity |

## Legacy naming (safe renames later)

| Pattern | Where |
|---------|--------|
| `Nexa` / `nexa_*` env | Widespread; OpenClaw parity paths |
| `NEXA_*` settings | `app/core/config.py` |
| Mission Control DB models `NexaMission` | Phase 1 parity |

## Stale / low-use surfaces

| Item | Action |
|------|--------|
| `GET /mission-control/summary` | Already 410 — keep |
| Legacy agent registry UI (`/mission-control/ceo`) | Distinct from `runtime_agents` — document only |
| Duplicate plugin registries | `app/plugins/*` vs `app/services/plugins/registry.py` — merged at load time |

## Tests to keep green before cleanup

- `tests/test_openclaw_*`
- `tests/test_mission_control_*`
- `tests/test_runtime_*`
- `tests/production_like/`

## Recommended next cleanup phase

1. Single `build_execution_snapshot` path calling `build_runtime_truth` once
2. Remove redundant `operator_context` duplication in runtime payload
3. Nexa → AethOS display strings in web nav only (non-breaking)
4. Archive unused Mission Control legacy components under `web/app/mission-control/legacy`

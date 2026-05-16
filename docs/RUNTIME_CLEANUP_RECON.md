# Runtime cleanup reconnaissance (Phase 2 Step 10–11)

## Completed (Step 11)

| Item | Status |
|------|--------|
| `runtime_truth.py` authoritative path | Done |
| `runtime_intelligence.py` cached truth (5s TTL) | Done |
| `nexa_next_state.build_execution_snapshot` MC fields from truth | Done |
| `runtime_lifecycle.py` bounded repair/deploy sweeps | Done |
| `runtime_ownership` trace bundles (repair/deployment/provider) | Done |
| `plugin_runtime.build_plugin_health_panel` | Done |
| Event aggregation + severity prioritization | Done |

## Completed (Step 15)

- Unified runtime identity (`runtime_identity`, canonical labels)
- Enterprise operator experience bundle on truth
- Runtime overview API and Mission Control page
- Duplicate timeline consolidation via `build_unified_governance_timeline`
- Cleanup progression score 0.92

## Completed (Step 16 — final lock)

- `runtime_truth_lock` — single authority validation
- `enterprise_readiness` / `runtime_readiness_score` on truth
- `production_hardening` bounds verification
- `runtime_discipline_completion` + `calmness_lock`
- Governance accountability summaries on truth
- `cleanup_completion_percentage` 0.97 — **locked**
- Deprecated paths catalog in `runtime_cleanup_completion.py`

## Remaining (post–Step 16)

| Location | Notes |
|----------|--------|
| `nexa_next_state.py` | DB mission payload still separate from orchestration truth (parity) |
| Duplicate plugin registries | `app/plugins/*` vs `app/services/plugins/registry.py` |

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

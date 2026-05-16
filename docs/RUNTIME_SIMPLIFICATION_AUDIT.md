# Runtime simplification audit (Phase 3 Step 3)

## Authoritative path

| Surface | Source |
|---------|--------|
| Mission Control runtime | `build_runtime_truth()` → `runtime_truth_cache` (5s TTL) |
| MC panels | `build_runtime_panels_from_truth(truth)` via cached `_truth()` |
| MC `/state` | `build_execution_snapshot` embeds truth-derived fields |
| Office | `build_office_operational_view(truth)` |
| Differentiators | `build_differentiators_summary(ort)` |

## Consolidated (Step 3)

- `runtime_panels.py` uses cached truth (no duplicate full builds)
- Office operational view derived from truth (no parallel `office_topology` read)
- Event aging + summary pruning on truth build
- Runtime discipline metrics (payload size, cache hit rate)

## Remaining (intentional)

| Item | Reason |
|------|--------|
| `nexa_next_state` DB mission slice | OpenClaw / Phase 1 parity |
| `app/services/plugins/registry.py` | Tool plugins vs runtime plugins |
| ClawHub marketplace vs runtime plugin marketplace | Different products |

See `docs/RUNTIME_DEPRECATIONS.md`.

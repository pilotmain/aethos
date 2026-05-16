# Runtime deprecations (Phase 3 Step 3–16)

## Deprecated patterns (do not extend)

| Pattern | Replacement |
|---------|-------------|
| Inline MC `runtime_health` in `nexa_next_state` | `build_runtime_truth()` |
| Direct `office_topology()` for MC Office API | `GET /mission-control/office` → `build_office_operational_view` |
| `build_runtime_panels` calling `build_runtime_truth` uncached | `_truth()` cache |
| Fake permanent agents beyond orchestrator | Dynamic workers with `persistent: false` |

## Step 16 locked paths

See `app/services/mission_control/runtime_cleanup_completion.py` → `DEPRECATED_RUNTIME_PATHS`.

| Path | Replacement |
|------|-------------|
| `build_runtime_truth_full` | `hydrate_runtime_truth_incremental` |
| Parallel governance timelines | `build_unified_governance_timeline` |
| Uncached MC truth rebuilds | `get_cached_runtime_truth` |

## Not deprecated (parity)

- `NexaMission` models and mission DB snapshot fields
- ClawHub skill marketplace (`/api/v1/marketplace/search`)
- Legacy CEO agent UI (`/mission-control/ceo`) — distinct from runtime agents

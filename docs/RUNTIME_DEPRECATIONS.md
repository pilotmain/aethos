# Runtime deprecations (Phase 3 Step 3)

## Deprecated patterns (do not extend)

| Pattern | Replacement |
|---------|-------------|
| Inline MC `runtime_health` in `nexa_next_state` | `build_runtime_truth()` |
| Direct `office_topology()` for MC Office API | `GET /mission-control/office` → `build_office_operational_view` |
| `build_runtime_panels` calling `build_runtime_truth` uncached | `_truth()` cache |
| Fake permanent agents beyond orchestrator | Dynamic workers with `persistent: false` |

## Not deprecated (parity)

- `NexaMission` models and mission DB snapshot fields
- ClawHub skill marketplace (`/api/v1/marketplace/search`)
- Legacy CEO agent UI (`/mission-control/ceo`) — distinct from runtime agents

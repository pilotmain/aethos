# Runtime resilience (Phase 4 Step 6)

Mission Control tolerates partial API failures via degraded operational states: `healthy`, `degraded`, `recovering`, `partial`, `offline`, `stale`.

## Backend

- `app/services/mission_control/runtime_resilience.py` — resilient slice fetch and degraded `/mission-control/state`
- `web/lib/runtimeResilience.ts` — panel-level fetch with stale cache fallback

## CLI

```bash
aethos runtime ping
aethos connection diagnose
aethos connection reset
```

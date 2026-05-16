# Mission Control finalization (Phase 3 Step 16)

## Primary surfaces

| Surface | Route |
|---------|--------|
| Office | `/mission-control/office` |
| Runtime overview | `/mission-control/runtime-overview` |
| Governance | `/mission-control/governance` |
| Operational insights | `/mission-control/operational-insights` |

All derive from `get_cached_runtime_truth` → `build_runtime_truth`.

## Deprecated

- `/mission-control/ceo` — use Office
- Legacy overview project metrics — complements runtime-overview

## Readiness

Runtime overview shows **enterprise readiness score** from `/runtime/readiness`.

Cleanup locked at **97%** — see `docs/RUNTIME_CLEANUP_RECON.md`.

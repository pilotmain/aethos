# Mission Control responsiveness

Phase 3 Step 12 routes prefer lightweight slices:

| Endpoint | Path |
|----------|------|
| Workers | `GET /mission-control/runtime/workers` |
| Deployments | `GET /mission-control/runtime/deployments` |
| Providers | `GET /mission-control/runtime/providers` |
| Governance | `GET /mission-control/runtime/governance` |
| Recommendations | `GET /mission-control/runtime/recommendations` |
| Intelligence | `GET /mission-control/runtime/intelligence` |
| Continuity | `GET /mission-control/runtime/continuity` |
| Health (enterprise) | `GET /mission-control/runtime/health` |
| Timeline (incremental) | `GET /mission-control/runtime/timeline` |
| Performance | `GET /mission-control/runtime/performance` |

Office and cohesion endpoints still use cached full truth when needed; warm slice + truth caches target sub-second reads for typical polling.

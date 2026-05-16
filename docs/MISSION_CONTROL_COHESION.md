# Mission Control cohesion (Phase 3 Step 15)

All operational pages should derive from **one authoritative runtime truth path**:

```
build_runtime_truth → hydrate_runtime_truth_incremental → summarize_truth_payload
```

Consolidated surfaces:

| Concern | Truth key / API |
|---------|-----------------|
| Overview | `runtime_overview`, `/runtime/overview` |
| Trust | `operational_trust_score`, `/governance/trust` |
| Calmness | `runtime_calmness`, `/runtime/calmness` |
| Workers | `worker_runtime_cohesion`, `/workers/overview` |
| Governance | `governance_experience`, `/governance/overview` |
| Providers | `/providers/overview` |

Cleanup progression tracked in `runtime_cohesion.cleanup_progression` (progress ~0.92).

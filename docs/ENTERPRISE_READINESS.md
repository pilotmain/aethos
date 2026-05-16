# Enterprise readiness (Phase 3 Step 16)

Production readiness scores on runtime truth:

| Key | Meaning |
|-----|---------|
| `runtime_readiness_score` | Composite 0–1 readiness |
| `operational_readiness` | Trust + calmness + quality |
| `deployment_readiness` | Deployment health and pressure |
| `governance_readiness` | Authoritative timeline + integrity |
| `scalability_readiness` | Payload budget + scalability health |
| `enterprise_readiness` | Bundle with `enterprise_ready` flag |

API: `GET /mission-control/runtime/readiness`  
CLI: `aethos runtime readiness`, `aethos operational-readiness`

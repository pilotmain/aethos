# Operational trust model

Measurable trust on authoritative runtime truth:

| Key | Purpose |
|-----|---------|
| `operational_trust_score` | Composite 0–1 score |
| `governance_integrity` | Audit and privacy event integrity |
| `runtime_accountability` | Cache, payload, orchestrator ownership |
| `provider_trust` | Provider failures and fallback |
| `automation_trust` | Pack execution trust |
| `worker_trust` | Worker reliability |

API: `GET /mission-control/governance/trust`  
CLI: `aethos governance trust`

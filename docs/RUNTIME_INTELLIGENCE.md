# Runtime intelligence (Phase 4 Step 5)

Phase 4 Step 5 adds unified runtime intelligence: adaptive routing, operational recovery, posture awareness, continuity, advisories, and governance intelligence.

## APIs

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/mission-control/runtime/intelligence` | Unified runtime intelligence |
| `GET /api/v1/mission-control/runtime/posture` | Operational posture |
| `GET /api/v1/mission-control/runtime/recovery` | Recovery engine visibility |
| `GET /api/v1/mission-control/runtime/routing` | Intelligent routing |
| `GET /api/v1/mission-control/runtime/continuity` | Continuity state |
| `GET /api/v1/mission-control/runtime/advisories` | Strategic recommendations |
| `GET /api/v1/mission-control/runtime/focus` | Operational focus mode |
| `GET /api/v1/mission-control/workers/intelligence` | Worker ecosystem intelligence |
| `GET /api/v1/mission-control/governance/intelligence` | Governance intelligence (Step 3 + Step 5) |
| `GET /api/v1/mission-control/enterprise/posture` | Enterprise operational posture |

## CLI

```bash
aethos runtime intelligence
aethos runtime posture
aethos runtime recovery
aethos runtime routing
aethos runtime continuity
aethos runtime advisories
aethos runtime focus
aethos workers intelligence
aethos governance intelligence
aethos enterprise posture
```

## Mission Control

- `/mission-control/runtime-intelligence` — unified intelligence dashboard

## Principles

All Step 5 behavior is **advisory-first**, **orchestrator-owned**, **bounded**, and **explainable**. No hidden autonomy.

# Workspace intelligence (Phase 3 Step 9)

Runtime-backed workspace awareness for Mission Control and operator continuity.

## Runtime truth keys

| Key | Purpose |
|-----|---------|
| `workspace_intelligence` | Projects, risk/deployment/repair signals, summaries |
| `research_chains` | Linked research deliverables + comparison history |
| `deliverable_relationships` | `derived_from`, `supersedes`, `continuation_of`, etc. |
| `operational_risk` | High-risk projects, churn, retry pressure |
| `operator_continuity` | Per-chat resume scope |

## APIs

- `GET /api/v1/mission-control/workspace-intelligence`
- `GET /api/v1/mission-control/workspace-risks`
- `GET /api/v1/mission-control/research-chains`
- `GET /api/v1/mission-control/operator-continuity`
- `GET /api/v1/mission-control/worker-collaboration`
- `GET /api/v1/mission-control/deliverables/{id}/relationships`

## CLI

```bash
aethos workspace summary
aethos workspace risks
aethos workspace research-chains
aethos deliverables compare <id1> <id2>
aethos workers continuity <worker_id>
```

## Operator continuity examples

- `continue where we left off`
- `show the latest deployment investigation`
- `continue the competitor analysis`
- `compare with previous findings`

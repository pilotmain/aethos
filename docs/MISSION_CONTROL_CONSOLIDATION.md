# Mission Control consolidation (Phase 3 Step 11)

Mission Control surfaces align under one operational identity:

| Surface | Route | Truth key |
|---------|-------|-----------|
| Office | `/office` | `office` |
| Runtime | `/overview` | `runtime_health` |
| Deliverables | `/deliverables` | `worker_deliverables` |
| Workspace | `/workspace-intelligence` | `workspace_intelligence` |
| Insights | `/operational-insights` | `operational_intelligence` |
| Governance | `/governance` | `unified_operational_timeline` |
| Marketplace | `/marketplace` | `marketplace` + `automation_packs` |

Secondary nav holds specialized views; all load from the same cached truth path.

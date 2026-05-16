# Enterprise runtime governance (Phase 3 Step 10)

Governance timeline includes automation pack executions, deliverables, continuations, and workspace governance events.

## Events

- `automation_pack_executed`, `automation_pack_failed`, `automation_pack_disabled`
- `research_continued`, `deliverable_compared`, `operational_risk_escalated`
- `workspace_degradation_detected`, `plugin_instability_detected`

API:

- `GET /api/v1/mission-control/governance`
- `GET /api/v1/mission-control/governance/risks`

CLI: `aethos governance timeline`, `aethos governance risks`

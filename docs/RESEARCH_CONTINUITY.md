# Research continuity (Phase 3 Step 9)

Research deliverables (`research_summary`) auto-link into **research chains** with optional `continuation_of` relationships to prior findings.

## Chain fields

- `research_chain_id`, `project_id`, `topic`, `worker_id`
- `related_deliverables`, `comparison_history`, `updated_at`

## Governance events

- `research_continued`, `deliverable_compared`, `continuation_resumed`, `workspace_risk_detected`

Bounded caps: 64 chains, 400 relationships, 120 governance events (runtime state).

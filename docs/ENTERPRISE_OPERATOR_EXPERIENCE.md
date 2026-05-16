# Enterprise operator experience (Phase 3 Step 15)

`enterprise_operator_experience` bundles:

- `runtime_identity` — canonical terminology
- `runtime_overview` — headline, trust, calmness, pressure
- `operational_narratives` — concise deployment/escalation/provider stories
- `runtime_stories` — enterprise storytelling surfaces
- `runtime_calmness` / `operational_quality` — calmness and quality scores
- `governance_experience` — unified governance UX
- `worker_cohesion` — unified worker state
- `enterprise_views` — all enterprise runtime surfaces

API: `GET /mission-control/runtime/overview`  
CLI: `aethos runtime overview`

Mission Control: **Runtime** nav → `/mission-control/runtime-overview`

## Phase 4 Step 8 — summary-first, calm operations

Operators see enterprise summaries before raw operational detail:

- `GET /api/v1/runtime/summaries` — operational, worker, governance, deployment, provider, continuity headlines
- `GET /api/v1/runtime/calmness-lock` — calmness integrity, noise score, escalation visibility
- `GET /api/v1/runtime/production-posture` — sustained operation and resilience posture
- `GET /api/v1/mission-control/workers/lifecycle` — maturity, specialization trust, archival lineage
- `GET /api/v1/mission-control/governance/index` — efficient governance windows and index health

Runtime overview fetches `/runtime/summaries` alongside existing overview/calmness endpoints. Office remains lightweight (cards + progressive stream), not a monitoring wall.

CLI: `aethos runtime summaries|calmness|posture|eras|partitions`, `aethos governance index`, `aethos workers lifecycle`.

## Phase 4 Step 9 — operational surfaces

- **Governance experience** — `/mission-control/governance-experience`
- **Worker ecosystem** — `/mission-control/workers/ecosystem`
- **Executive overview** — `/mission-control/executive-overview`
- **Runtime story** — `/mission-control/runtime-story`
- **Explainability** — `/mission-control/explainability`
- **Timeline experience** — `/mission-control/timeline-experience`

Enterprise language system calms technical terms for operator trust. See [MISSION_CONTROL_LANGUAGE_SYSTEM.md](MISSION_CONTROL_LANGUAGE_SYSTEM.md).

## Phase 4 Step 13 — launch-grade operator experience

- **Office** — operational command center (health, readiness, orchestrator, active work)
- **Recovery** — reconnecting copy via `recovery_experience` (not “connection failed”)
- `GET /api/v1/runtime/operator-experience`, `/operational-focus`, `/priority-work`, `/noise-reduction`, `/calmness-metrics`, `/signal-health`
- Certification: [LAUNCH_READINESS_CERTIFICATION.md](LAUNCH_READINESS_CERTIFICATION.md)

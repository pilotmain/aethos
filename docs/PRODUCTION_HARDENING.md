# Production hardening (Phase 3 Step 16)

`production_hardening` verifies bounded runtime surfaces:

- Payload within `AETHOS_TRUTH_PAYLOAD_MAX_BYTES`
- Timeline window ≤ 48 entries
- Deliverable list capped on truth
- Governance and continuity presence

Truth key: `production_hardening` with `resilient` aggregate flag.

Included in `GET /mission-control/operational-readiness`.

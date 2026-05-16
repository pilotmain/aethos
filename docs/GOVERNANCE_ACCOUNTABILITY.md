# Governance accountability

Step 14 unifies governance into one authoritative timeline via `build_unified_governance_timeline()`:

- Deduplicates provider, deployment, repair, automation, worker, and escalation events
- Merges with recommendations and risk signals from truth
- Exposes `unified_operational_timeline.authoritative = true`

Search and filter remain on `/governance/search` and `/governance/filter`.

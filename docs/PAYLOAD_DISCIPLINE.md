# Payload discipline

`summarize_truth_payload()` caps list fields before truth is returned:

- Events, deliverables, continuations, recommendations
- Governance audit sections
- Worker and deployment summaries

Metrics persist in `payload_discipline_metrics` on `aethos.json`:

- `payload_growth_rate` / `payload_reduction_rate`
- `oversized_payload_events`
- `collapsed_payload_sections`
- `timeline_summary_ratio`

Use `aethos runtime payloads` or truth key `payload_discipline` for live status.

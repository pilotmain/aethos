# Governance searchability

Governance timeline entries are searchable and filterable without loading full history.

## Search

`GET /mission-control/governance/search?q=provider`

Matches `what`, `who`, `kind`, `provider`, and related fields.

## Filter

`GET /mission-control/governance/filter?kind=deployment&actor=runtime`

Supported filters: `severity`, `actor`, `kind`/`category`, `provider`, `worker_id`, `deployment_id`.

## CLI

```bash
aethos governance search provider
aethos governance filter --kind deployment
```

Mission Control governance page uses search + kind filter with bounded timeline windows.

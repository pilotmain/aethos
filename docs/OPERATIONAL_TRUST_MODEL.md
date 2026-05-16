# Operational trust model

AethOS builds operator trust through **visible ownership**, **bounded history**, and **honest health** — not compliance theater.

## Trust pillars

| Pillar | Surface |
|--------|---------|
| Runtime truth | Single `build_runtime_truth()` path, 5s cache |
| Confidence | `runtime_confidence` — uptime, restarts, 24h failures |
| Governance | Human timeline — deployments, repairs, providers, brain, privacy, plugins, packs |
| Privacy | Operational posture + egress decisions |
| Providers | Inventory, auth status, reliability summary |
| Plugins | Sandboxed, health-counted, recoverable |
| Brain routing | Confidence score, fallback frequency, privacy mode |

## What we do not claim

- Full enterprise RBAC (lightweight ownership only)
- Billing-grade cost accounting (estimates only)
- Guaranteed SLA metrics (operational signals only)

## Operator question

> Can I trust this runtime right now?

Answer via Office **Runtime confidence** card + `/runtime-confidence` API.

# Final legacy naming policy

## Operator-facing (must say AethOS)

CLI help, Mission Control UI, setup/install scripts, Telegram copy, API error messages.

## Allowed legacy

| Term | Where |
|------|--------|
| OpenClaw | README inspiration, `docs/OPENCLAW_*`, `tests/test_openclaw_*` |
| Nexa | `NEXA_*` env aliases, migration internals, compatibility wrappers |
| ClawHub/OpenHub | Internal migration only; prefer **AethOS Marketplace** / **AethOS Skills** in UI |

## Scan

```bash
scripts/scan_legacy_branding.sh --operator-facing
scripts/scan_legacy_branding.sh --full
```

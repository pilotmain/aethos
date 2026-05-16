# Final legacy policy

## User-facing brand

**AethOS** everywhere operators read product copy.

## Nexa — allowed only

- `NEXA_*` environment aliases (see [COMPATIBILITY_ALIAS_POLICY.md](COMPATIBILITY_ALIAS_POLICY.md))
- Migration and compatibility layers
- Internal compatibility tests and docs

## OpenClaw — allowed only

- README inspiration line
- `docs/OPENCLAW_*` parity directive
- `tests/test_openclaw_*` parity verification

## Enforcement

- `build_final_legacy_policy()` on runtime truth (Step 13)
- `aethos setup certify` branding scans (CLI + UI)

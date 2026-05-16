# Branding convergence (final) — Step 17

Phase: `phase4_step17`. Scan: `scripts/scan_legacy_branding.sh`.

Operator-visible surfaces target **AethOS** only. See `docs/FINAL_LEGACY_POLICY.md` and `docs/COMPATIBILITY_ALIAS_POLICY.md`.

| Allowed | Where |
|---------|--------|
| OpenClaw | README inspiration, parity docs/tests |
| Nexa | `NEXA_*` env aliases, migration internals |

**API:** `GET /api/v1/runtime/branding-audit`  
**CLI:** `aethos runtime branding-audit`

Module: `branding_convergence_final.py`

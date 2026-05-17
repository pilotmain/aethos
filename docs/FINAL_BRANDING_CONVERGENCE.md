# Final branding convergence (Phase 4 Step 21)

Operator-visible surfaces should read **AethOS** everywhere. Remaining legacy terms are classified by `final_branding_convergence_audit.py`:

- `operator_critical` / `operator_visible` — must remove from UI/CLI
- `compatibility_required` — `NEXA_*` env aliases
- `parity_required` — OpenClaw parity tests/docs
- `historical_allowed` — migration and inspiration notes

CLI: `aethos runtime branding-audit`  
API: `GET /api/v1/runtime/branding-audit`, `GET /api/v1/runtime/branding-convergence`

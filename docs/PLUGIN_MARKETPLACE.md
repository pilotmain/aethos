# Plugin marketplace foundation (Phase 2 Step 9)

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/plugins/` | List plugin metadata |
| GET | `/api/v1/plugins/{id}` | Single plugin |
| POST | `/api/v1/plugins/load` | Load → `active` |
| POST | `/api/v1/plugins/disable` | Disable plugin |

## Metadata

Each plugin exposes: `plugin_id`, `author`, `version`, `capabilities`, `permissions`, `verified`, `installed`, `runtime_state`.

Full marketplace UI is a future milestone; this phase provides runtime-safe loading and visibility only.

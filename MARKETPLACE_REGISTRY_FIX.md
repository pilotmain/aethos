# Marketplace Registry Fix — Remote ClawHub Unavailable

## Problem

The default upstream registry (`NEXA_CLAWHUB_API_BASE`, commonly `https://clawhub.com/api/v1`) may redirect, return non-JSON, or 404. Mission Control then showed **empty** search/popular/featured results (`{"ok": true, "skills": []}`).

## What We Implemented (AethOS)

### 1. Bundled fallback catalog

- **`data/aethos_marketplace/fallback_skills.json`** — committed skill stubs (metadata only; **not** installable archives).
- **`app/services/skills/registry_fallback.py`** — merges **built-in** stubs with the JSON file, dedupes by name, filters search by query/category.

### 2. `ClawHubClient` integration

**`app/services/skills/clawhub_client.py`**:

- After a failed remote call **or** empty parsed results, when fallback is enabled, **`search_skills`**, **`list_popular`**, **`list_featured`**, and **`get_skill_info`** use the bundled catalog.
- Uses **`httpx` `follow_redirects=True`** (same as before; upstream misconfiguration is detected via status / JSON parse).
- Logs `clawhub … using fallback catalog` when fallback is used.

### 3. Settings (`app/core/config.py`)

| Field | Env | Default |
|-------|-----|---------|
| `nexa_clawhub_fallback_enabled` | `NEXA_CLAWHUB_FALLBACK_ENABLED` | `true` |
| `nexa_clawhub_fallback_catalog_path` | `NEXA_CLAWHUB_FALLBACK_CATALOG_PATH` | repo `data/aethos_marketplace/fallback_skills.json` |

Relative paths resolve against **repo root**.

### 4. Operator probe

**`GET /api/v1/marketplace/-/registry-status`** (web auth) returns:

- `configured_api_base`, `reachable`, `http_status`, `json_ok`, `fallback_enabled`, `fallback_skill_count`, plus **`ClawHubClient.probe_remote()`** details.

### 5. Rollback / tuning

- Disable fallback: **`NEXA_CLAWHUB_FALLBACK_ENABLED=false`** (empty results again if remote is dead).
- Disable all remote ClawHub traffic: **`NEXA_CLAWHUB_ENABLED=false`** (install/search from upstream stop; fallback only applies when ClawHub is enabled — keep **`NEXA_CLAWHUB_ENABLED=true`** for fallback-on-empty behavior).

### 6. Testing

- `tests/test_registry_fallback.py`, `tests/test_clawhub_fallback.py`
- `tests/test_marketplace_api_phase71.py` — `/-/registry-status`
- `./scripts/test_marketplace.sh` — calls registry status after `/health`

## Optional future work

- Point **`NEXA_CLAWHUB_API_BASE`** at a live compatible registry if one exists.
- Extend **`fallback_skills.json`** or replace it operator-side with a fuller mirror.
- Cache-last-success responses to disk (TTL) — not implemented in v1; bundled file is the offline source of truth.

## Related docs

- `MARKETPLACE_AND_ASSIGNMENT_FIXES.md` — marketplace routes and auth.

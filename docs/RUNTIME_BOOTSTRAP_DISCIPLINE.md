# Runtime bootstrap discipline

Setup seeds automatically:

- `web/.env.local` — API base + user id
- Repo `.env` — bearer, aliases, compatibility version
- `~/.aethos/mc_browser_bootstrap.json` — browser bootstrap payload
- Setup creds merge via `merge_setup_creds`

**API:** `GET /api/v1/runtime/bootstrap`  
**CLI:** `aethos runtime bootstrap`

Localhost Mission Control should work without manual token entry after `aethos setup`.

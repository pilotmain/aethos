# ClawHub marketplace (Phase 17, Phase 71)

Install, update, and remove **plugin skills** from a remote ClawHub-compatible registry. Coexists with Phase 6 pluggable skills (`docs/SKILLS_SYSTEM.md`) and stores disk state under `NEXA_CLAWHUB_SKILL_ROOT` (default `data/skills/`).

> **Phase 71** added the user-facing surfaces on top of the Phase 17 backend: a Mission Control **Marketplace** panel (web), a `/skills_*` family of Telegram commands, and a parallel web-auth API at `/api/v1/marketplace/*` so the browser doesn't need the cron-only token. The underlying client / installer / `installed.yaml` manifest are unchanged.

## Configuration

| Env | Default | Purpose |
|-----|---------|---------|
| `NEXA_CLAWHUB_ENABLED` | `true` | Disable all remote calls when `false`. |
| `NEXA_CLAWHUB_API_BASE` | `https://clawhub.com/api/v1` | Registry base URL (same as Phase 6). |
| `NEXA_CLAWHUB_SKILL_ROOT` | `<repo>/data/skills` | Extracted packages + `installed.yaml` manifest. |
| `NEXA_CLAWHUB_TRUSTED_PUBLISHERS` | _(empty)_ | Comma list (case-insensitive). Empty = **no** publisher filter. Non-empty = installs allowed only from listed publishers. |
| `NEXA_CLAWHUB_REQUIRE_SIGNATURE` | `false` | When `true`, reject installs whose catalog metadata has no `signature`. |
| `NEXA_CLAWHUB_AUTO_UPDATE` | `false` | Reserved for future background refresh (not wired in v1). |
| `NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL` | `false` | When `true`, HTTP install refuses unless callers pass installer **`force`** (CLI: `--force`). |
| `NEXA_MARKETPLACE_PANEL_ENABLED` | `true` | Phase 71 — kill switch for the Mission Control Marketplace web panel + `/api/v1/marketplace/*` proxy. Set to `false` to disable browser access without disabling the cron automation surface. |

The Phase 17 cron-token surface and the Phase 71 web-auth surface are independent kill switches:

- Setting `NEXA_CRON_API_TOKEN=` disables `/api/v1/clawhub/*` (HTTP 503) but the web Marketplace panel still works.
- Setting `NEXA_MARKETPLACE_PANEL_ENABLED=false` disables the web Marketplace panel + `/api/v1/marketplace/*` (HTTP 503) but cron-driven `/api/v1/clawhub/*` automations still work.
- Setting `NEXA_CLAWHUB_ENABLED=false` disables both (the underlying client returns empty results for every call).

## REST APIs

### Cron automation — `/api/v1/clawhub` (Phase 17)

`Authorization: Bearer <NEXA_CRON_API_TOKEN>` (same gate as `POST /api/v1/cron/*`). Unset token → HTTP 503.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search?q=&limit=` | Search catalog. |
| GET | `/popular?limit=` | Popular skills. |
| GET | `/skill/{name}` | Metadata for one skill. |
| POST | `/install` | JSON `{ "name", "version": "latest" }`. |
| POST | `/uninstall/{name}` | Remove from disk, registry, manifest. |
| POST | `/update/{name}` | Re-fetch latest metadata and reinstall if newer. |
| GET | `/installed` | Local manifest entries. |

### Web panel — `/api/v1/marketplace` (Phase 71)

Standard web auth (`X-User-Id` plus optional `Authorization: Bearer <NEXA_WEB_API_TOKEN>` when configured). Mutating endpoints additionally require the **Telegram-linked owner** role (same gate the rest of the destructive web surface uses). Disabled with HTTP 503 when `NEXA_MARKETPLACE_PANEL_ENABLED=false`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/search?q=&limit=` | web user | Search catalog. |
| GET | `/popular?limit=` | web user | Popular skills. |
| GET | `/skill/{name}` | web user | Metadata for one skill. |
| GET | `/installed` | web user | Local manifest entries. |
| POST | `/install` | **owner** | JSON `{ "name", "version": "latest", "force": false }`. |
| POST | `/uninstall/{name}` | **owner** | Remove from disk + plugin registry + manifest. |
| POST | `/update/{name}?force=` | **owner** | Re-fetch + reinstall if newer. |

The web client lives at `web/lib/api/marketplace.ts` and the page at `/mission-control/marketplace`.

## CLI

```bash
python -m nexa_cli --user-id web_dev clawhub search "git" --limit 10
python -m nexa_cli clawhub popular
python -m nexa_cli clawhub install my_skill --version latest
python -m nexa_cli clawhub list-installed
python -m nexa_cli clawhub uninstall my_skill
python -m nexa_cli clawhub update my_skill
```

## Telegram (Phase 71)

Mutating commands require the workspace **owner** role; everything else is open to any non-blocked Telegram user.

| Command | Owner only? | Description |
|---------|-------------|-------------|
| `/skills_search <query>` | no | Search the configured ClawHub registry (top 10). |
| `/skills_popular` | no | List popular skills (top 10). |
| `/skills_list` | no | List installed marketplace skills. |
| `/skills_install <name> [version]` | **yes** | Install a skill (default `version=latest`). |
| `/skills_uninstall <name>` | **yes** | Remove an installed skill. |
| `/skills_update <name>` | **yes** | Re-fetch and reinstall if a newer version exists. |

## Web Marketplace panel (Phase 71)

`Mission Control → Marketplace`:

- Search bar (proxies `GET /api/v1/marketplace/search`).
- Installed-skills section with **Uninstall** / **Check for update** per row (owner only — non-owners get HTTP 403 from the proxy).
- "Popular on ClawHub" section, refreshable.
- Install button on every search / popular result. Already-installed skills show an `installed` badge and disable the button.
- Errors from the underlying installer (`publisher_not_trusted`, `signature_required_missing`, `already_installed`, `clawhub_disabled`, `remote_metadata_unavailable`, `download_failed`) surface inline on the row.

## Docker

`docker-compose.yml` bind-mounts `./data/skills` → `/app/data/skills` for the API container so installs survive restarts.

## Safety notes

- **Trusted publishers** narrow who may be installed when the allowlist is non-empty.
- **Signature requirement** is metadata-only in v1 (no cryptographic verification unless extended later).
- **Egress**: registry host should appear in `NEXA_NETWORK_ALLOWED_HOSTS` when egress allowlists are enforced.
- **Owner gate** on the Phase 71 web/Telegram surfaces means a guest web user can browse and inspect remote skills, but cannot install code that gets registered into the plugin registry.

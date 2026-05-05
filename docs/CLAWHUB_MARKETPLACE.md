# ClawHub marketplace (Phase 17)

Install, update, and remove **plugin skills** from a remote ClawHub-compatible registry. Coexists with Phase 6 pluggable skills (`docs/SKILLS_SYSTEM.md`) and stores disk state under `NEXA_CLAWHUB_SKILL_ROOT` (default `data/skills/`).

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

REST endpoints use the **cron automation** gate: `Authorization: Bearer <NEXA_CRON_API_TOKEN>` (same as `POST /api/v1/cron/*`). Unset token → HTTP 503 on those routes.

## REST API (`/api/v1/clawhub`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search?q=&limit=` | Search catalog. |
| GET | `/popular?limit=` | Popular skills. |
| GET | `/skill/{name}` | Metadata for one skill. |
| POST | `/install` | JSON `{ "name", "version": "latest" }`. |
| POST | `/uninstall/{name}` | Remove from disk, registry, manifest. |
| POST | `/update/{name}` | Re-fetch latest metadata and reinstall if newer. |
| GET | `/installed` | Local manifest entries. |

## CLI

```bash
python -m nexa_cli --user-id web_dev clawhub search "git" --limit 10
python -m nexa_cli clawhub popular
python -m nexa_cli clawhub install my_skill --version latest
python -m nexa_cli clawhub list-installed
python -m nexa_cli clawhub uninstall my_skill
python -m nexa_cli clawhub update my_skill
```

## Docker

`docker-compose.yml` bind-mounts `./data/skills` → `/app/data/skills` for the API container so installs survive restarts.

## Safety notes

- **Trusted publishers** narrow who may be installed when the allowlist is non-empty.
- **Signature requirement** is metadata-only in v1 (no cryptographic verification unless extended later).
- **Egress**: registry host should appear in `NEXA_NETWORK_ALLOWED_HOSTS` when egress allowlists are enforced.

# Guided CLI login for Nexa operators

This document describes **why** Telegram/API workflows cannot “open a terminal,” how **Docker vs host** differs for `vercel` / `gh`, and how Nexa **surfaces copy-paste login steps** when CLIs are installed but not authenticated.

## Implementation (this repo)

| Piece | Location |
|-------|----------|
| Auth pattern detection + Markdown guidance | `app/services/operator_auth_guidance.py` |
| Vercel runner appends guidance | `app/services/operator_runners/vercel.py` |
| GitHub runner appends guidance | `app/services/operator_runners/github.py` |
| Feature flag | `NEXA_OPERATOR_CLI_AUTH_GUIDANCE` → `Settings.nexa_operator_cli_auth_guidance` |
| Docker container name in examples | `NEXA_OPERATOR_GUIDANCE_DOCKER_CONTAINER` or `Settings.nexa_operator_guidance_docker_container` |

Guidance is appended **only** when stderr/stdout match known “not logged in” phrases — not for missing binaries (`vercel_cli_missing` / `gh_cli_missing`).

## Credential persistence (Docker)

CLIs store login state under the container user’s home (default **`root`**):

| CLI | Typical path in container |
|-----|---------------------------|
| Vercel | `/root/.vercel` |
| GitHub CLI | `/root/.config/gh` |

Optional Compose volumes (commented in `docker-compose.yml`) can persist these across **restarts**. Rebuilds still need login if volumes are not used.

## Security

- Guidance text **never** asks users to paste tokens into Telegram.
- Token fallbacks are documented as **environment-only** (`VERCEL_TOKEN`, `GITHUB_TOKEN` / `GH_TOKEN`).

## Manual verification

After interactive login inside the API container:

```bash
docker exec -it nexa-api sh -c 'vercel whoami && gh auth status'
```

Use `sh -c` so shell builtins like `command -v` work as documented in `docs/SETUP.md`.

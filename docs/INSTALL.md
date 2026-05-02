# Installing Nexa-next

Phase 52 adds a **privacy-first** installation path alongside the existing bootstrap.

## One-line install

From an empty directory (canonical upstream script clones the default repo — set `NEXA_REPO_URL` to this repository if needed):

```bash
curl -fsSL https://pilotmain.com/install.sh | bash
```

Already cloned:

```bash
./scripts/install.sh --no-clone
```

## Dry run

No file changes and no services started:

```bash
./scripts/install.sh --no-clone --dry-run
```

## Local Postgres (Docker)

If `.env` uses `postgresql://127.0.0.1:…`, start the bundled DB before the API or Telegram bot:

```bash
./scripts/docker_postgres_up.sh
```

One command for local dev (default: **`docker compose up --build -d`** for db + api + bot, then host Next.js → Mission Control uses Docker API **:8010**):

```bash
./scripts/nexa_next_local_all.sh start
```

Host-only API with hot reload (no compose api/bot containers):

```bash
NEXA_NEXT_LOCAL_FULL_STACK=0 ./scripts/nexa_next_local_all.sh start
```

## Defaults

- Prefer **local / BYOK** configuration: add keys via `/key set` or `.env`, not inline chat.
- Review **`docs/SETUP.md`** for Postgres vs SQLite, Docker, and Telegram.

## Mission Control & API

After start (see `scripts/install.sh` output):

- API health: `http://127.0.0.1:8000/api/v1/health` (port from `PORT`)
- Web UI: `http://localhost:3000` when the web dev server is running

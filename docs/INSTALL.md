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

## Defaults

- Prefer **local / BYOK** configuration: add keys via `/key set` or `.env`, not inline chat.
- Review **`docs/SETUP.md`** for Postgres vs SQLite, Docker, and Telegram.

## Mission Control & API

After start (see `scripts/install.sh` output):

- API health: `http://127.0.0.1:8000/api/v1/health` (port from `PORT`)
- Web UI: `http://localhost:3000` when the web dev server is running

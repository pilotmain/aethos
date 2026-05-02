# Nexa-Next — Docker + Telegram + Startup (current state)

Post-`9ce08fa`, default local startup uses the **full Docker Compose stack** plus host Next.js.

## Recommended default

```bash
cd /path/to/nexa-next
./scripts/nexa_next_local_all.sh start
```

What this does:

- Runs **`docker compose up --build -d`**, starting **nexa-db**, **nexa-api** (published host port **8010** by default), **nexa-bot**.
- Starts **Next.js** on **`http://127.0.0.1:3120`** (override with **`NEXA_NEXT_WEB_PORT`**).
- Mission Control should use API base **`http://127.0.0.1:8010`** (Compose API).

## Alternative modes

**Host-only stack** (native uvicorn + optional host bot + Postgres sidcar / `docker_postgres_up`):

```bash
NEXA_NEXT_LOCAL_FULL_STACK=0 ./scripts/nexa_next_local_all.sh start
```

**Postgres container only** (for host processes connecting via `127.0.0.1:${POSTGRES_HOST_PORT}`):

```bash
./scripts/docker_postgres_up.sh
```

**Bot only, SQLite sidcar** (no Postgres daemon required on the host):

```bash
./scripts/run_telegram_bot_local.sh
```

## Networking

| Where | Database address |
|-------|-------------------|
| Inside Compose (api, bot containers) | `db:5432` |
| From your Mac (host Python / `.env`) | `127.0.0.1:5434` or **`POSTGRES_HOST_PORT`** |

Having **`DATABASE_URL`** use `@db:5432` in Compose **and** **`POSTGRES_HOST_PORT=5434`** for host mapping is normal—not a mismatch.

## Telegram bot — healthy logs

If **`docker compose logs bot`** shows **`getMe` 200**, **`Application started`**, **`getUpdates` 200**, the bot process is running. Use **`docker compose logs -f bot`** while testing.

## Required checks

| Check | Command / URL |
|-------|------------------|
| Containers | `docker compose ps` |
| API health | `http://127.0.0.1:8010/api/v1/health` (Compose API port; see **`NEXA_NEXT_COMPOSE_API_PORT`**) |
| Token present | `grep TELEGRAM_BOT_TOKEN .env` (ensure repo `.venv` and this repo’s `.env`) |

Send **`/start`** to the bot and watch **`docker compose logs -f bot`**.

## Known noisy warnings (often safe)

Examples: wrong **`DEV_EXECUTOR_PYTHON`** path, missing workspace root, port mismatch hints—these often do **not** stop Telegram polling by themselves.

## Common failure causes

- Messaging a **different** bot than the token in `.env`.
- **Token** typo, extra quotes, or wrong `.env` file loaded.
- Expecting replies without sending **`/start`** first (depending on bot UX).
- Using **`python`** from the wrong venv (use **`nexa-next/.venv`** for repo-local commands).

## Commit reference (startup / Docker / Telegram ops)

`289b8f4` · `883dcf0` · `786dc6d` · `9ce08fa`

## Model change at a glance

| Before | After |
|--------|--------|
| Often SQLite sidcar by default for `nexa_next_local_all.sh` | Default **`docker compose up --build -d`** + host Next.js; host API/bot skipped in that mode |

When Compose logs show a healthy bot but Telegram still misbehaves, verify **token chat routing** (correct bot, correct user, `/start`) before assuming Docker or DB failure.

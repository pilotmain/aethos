# Runtime recovery actions

| Command | Behavior |
|---------|----------|
| `aethos runtime takeover --yes` | Force ownership (requires `--yes`) |
| `aethos runtime release` | Release locks owned by this process |
| `aethos restart runtime` | Stop API+bot, restart API with ownership |
| `aethos restart bot` | Embedded-aware; no duplicate pollers |
| `aethos restart api` | Restart API only |

Only AethOS process patterns are stopped (`uvicorn app.main:app`, `app.bot.telegram_bot`).

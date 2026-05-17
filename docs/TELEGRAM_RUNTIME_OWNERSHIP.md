# Telegram runtime ownership

Embedded API mode (`NEXA_TELEGRAM_EMBED_WITH_API=true`) polls inside the API process. Standalone mode uses `python -m app.bot.telegram_bot`. Only one poller per token.

Calm messages via `telegram_ownership_ux.py`. Inspect: `aethos runtime services`. Restart embedded: `aethos restart runtime` or `aethos restart api`.

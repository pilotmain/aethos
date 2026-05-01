# Multi-user, roles, and BYOK

Nexa can be shared: each person can **bring their own** OpenAI and Anthropic API keys (BYOK) so chat, planning, and tools do not have to use the host’s `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` when the user has stored their own.

1. The owner runs Nexa (API, bot, database) with the [quick start](SETUP.md#quick-start-recommended) (or full Docker) path.
2. In Telegram, open the bot and send `/start`.
3. Add a key, e.g. `/key set openai sk-…` or `/key set anthropic sk-ant-…`
4. Check what is on file: `/key list` or `/keys` (full keys are never displayed).

**Encryption:** keys are **encrypted in the database**; only usage at run time is possible with a consistent `NEXA_SECRET_KEY` on the server. A user key is **for LLM calls** — it does **not** grant Dev Agent, Ops, or owner-only commands. Those are controlled by Telegram role configuration (see `.env.example`: `TELEGRAM_OWNER_IDS`, `TELEGRAM_TRUSTED_USER_IDS`, and optional block lists). Use `/access` in the bot to see what is enabled for your account.

For a single-tenant or homelab host, the same file documents how the owner vs guests differ.

# Full AethOS environment activation

## Problem

A minimal `.env` disables anything not listed. A fuller backup (e.g. `.env.bak`) can restore feature flags and optional integrations **without** changing keys you have already set in the active `.env`.

## Goal

1. **Merge** `.env.bak` into `.env` so **current values always win** on duplicate keys.
2. **Add** any variable that exists only in the backup.
3. **Deduplicate** keys in the output (one assignment per key).
4. **Validate** with `scripts/validate_aethos_env.py` (loads `Settings` from `app/core/config.py`).

## What we ship in the repo

| Path | Purpose |
|------|---------|
| `scripts/merge_aethos_env.py` | Merge `.env.bak` → `.env`, backup current to `.env.pre_full_backup` |
| `scripts/validate_aethos_env.py` | Load `.env`, construct `Settings`, print checklist |
| `.env.example` | Committed template — **no secrets** (keep aligned when adding `Settings` fields) |

**Never commit** `.env`, `.env.bak`, or `.env.pre_full_backup` — they are gitignored via `.env.*`.

## Commands

From the repo root (venv active):

```bash
# Preview how many keys would be added (no writes)
python scripts/merge_aethos_env.py --dry-run

# Merge: backs up current .env to .env.pre_full_backup, writes merged .env
python scripts/merge_aethos_env.py

# Validate Settings after merge
python scripts/validate_aethos_env.py
```

Optional:

```bash
python scripts/merge_aethos_env.py --bak .env.other_backup
```

## Merge semantics

- Parsed as `KEY=value` lines (comments and blank lines ignored in the parse step).
- **Union** of backup + current; **current overrides** backup for the same key.
- Output file is **sorted by key** with a short generated header. Section comments from `.env.bak` are **not** preserved (tradeoff for deterministic, duplicate-free files).

## Security

- `.env.bak` often contains **real secrets**. After merging, **rotate** any token that may have been copied from an old backup you no longer trust.
- **SMTP / OAuth / third-party tokens**: confirm values before enabling outbound email or social integrations.
- Prefer **minimal** secrets on disk; use env-specific files outside the repo if needed.

## Feature documentation

Authoritative names and defaults live in **`app/core/config.py`** (`Settings`) and **`/.env.example`**. Important groups:

| Area | Typical env vars | Notes |
|------|------------------|--------|
| Core | `APP_NAME`, `APP_ENV`, `DEBUG`, `DATABASE_URL`, `NEXA_SECRET_KEY` | `NEXA_SECRET_KEY` used for web/crypto helpers |
| LLM | `USE_REAL_LLM`, `ANTHROPIC_*`, `OPENAI_*`, `NEXA_LLM_*` | At least one provider key for real LLM calls |
| Telegram | `TELEGRAM_BOT_TOKEN`, `NEXA_TELEGRAM_EMBED_WITH_API` | Set embed false if you run `python -m app.bot.telegram_bot` standalone |
| Orchestration | `NEXA_AGENT_ORCHESTRATION_ENABLED`, `NEXA_WORKSPACE_ROOT`, `HOST_EXECUTOR_WORK_ROOT` | Registry + host paths |
| Self-improvement | `NEXA_SELF_IMPROVEMENT_*` | Off by default; enable deliberately |
| Skills / marketplace | `NEXA_CLAWHUB_*` | Skill catalog API base URL |
| Sandbox | `NEXA_SANDBOX_MODE`, `NEXA_REQUIRE_SANDBOX_FOR_SKILLS` | Execution isolation |

## Rollback

```bash
cp .env.pre_full_backup .env
```

Then restart the API and bot.

## Getting API keys (high level)

- **OpenAI / Anthropic**: provider dashboards → API keys.
- **Telegram**: BotFather → bot token.
- **GitHub / Vercel / Railway**: respective developer settings (tokens are optional unless you use those integrations).

Features that **cannot** work without real credentials: cloud LLM calls, Telegram delivery, paid third-party APIs you configure.

# AethOS branding and owner recognition

This document describes the permanent approach for **product naming** and **privileged-owner** checks.

## Branding (`app/core/branding.py`)

- User-facing strings use **`display_product_name()`** (from `Settings.aethos_brand_name` / `app_name`, overridable via **`AETHOS_BRAND_NAME`**).
- **`substitute_legacy_product_name(text)`** replaces the standalone word **Nexa** with the configured product name. It does **not** rewrite `NEXA_*` env tokens or identifiers.

## Unified owner list (`AETHOS_OWNER_IDS`)

- **`aethos_owner_ids`** in `Settings` ← env **`AETHOS_OWNER_IDS`** (comma-separated canonical ids like `tg_*`, `web_*`).
- **`is_privileged_owner_for_web_mutations`** checks this list **first**, then Telegram owner role (`TELEGRAM_OWNER_IDS` / bootstrap), then governance role and org membership.

`TELEGRAM_OWNER_IDS` remains **numeric** Telegram user ids (existing behavior). To grant Mission Control owner-class APIs by canonical app user id without relying on Telegram bootstrap alignment, set **`AETHOS_OWNER_IDS`** accordingly.

### Migrating existing `.env`

Run from the repo root:

```bash
chmod +x scripts/fix_owner_config.sh
./scripts/fix_owner_config.sh
```

The script appends **`AETHOS_OWNER_IDS`** derived from **`TELEGRAM_OWNER_IDS`** (numeric ids become **`tg_<id>`**). If neither **`TELEGRAM_OWNER_IDS`** nor **`NEXA_SELF_IMPROVEMENT_OWNER_ID`** is set, add **`AETHOS_OWNER_IDS`** manually.

## Tests

- `tests/test_branding.py` — brand name and substitution.
- `tests/test_privileged_web_owner.py` — governance, org membership, and **`AETHOS_OWNER_IDS`**.

## Operational notes

- Do **not** apply a naive global replace of `NEXA` in arbitrary strings (would corrupt env var names and code tokens).
- After changing env-driven branding or owner lists, restart processes that cache settings (API, Telegram bot).

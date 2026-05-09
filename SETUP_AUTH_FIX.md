# AethOS setup wizard — authentication & verification

## Problem (fixed)

With `NEXA_WEB_API_TOKEN` set, protected routes require **both** `X-User-Id` and `Authorization: Bearer`. The wizard generated a token but used a hard-coded `X-User-Id` in verification, so new users often saw **401** on the “Agents” / “Marketplace” checks.

## What changed

1. **Step 4 — Authentication** (after environment, before database):
   - Prompts for a valid **X-User-Id** (validated with `app.services.web_user_id.validate_web_user_id`).
   - Persists it as **`TEST_X_USER_ID`** in `.env` (for the web UI to mirror).
   - Optional **Telegram** token; if the user id is `tg_<digits>`, appends the numeric id to **`TELEGRAM_OWNER_IDS`**.
   - Prints the full **`NEXA_WEB_API_TOKEN`** and writes **`~/.aethos_credentials`**.

2. **Verification (step 8)** uses `TEST_X_USER_ID` + bearer token for auth’d checks; public health check unchanged. On **401**, prints a short hint.

3. **Completion banner** shows API base, user id, masked token, and points to **`./scripts/show_credentials.sh`**.

4. **`scripts/show_credentials.sh`** — safe `.env` parse (no broken `export $(grep …)`), health probe.

## Step order (8 total)

Requirements → Dependencies → Environment → **Authentication** → Database → LLM keys → Services → Verify.

## Rollback

```bash
git checkout HEAD~1 -- scripts/setup.py scripts/setup_helpers/help_system.py  # adjust as needed
```

(Prefer `git log` to find the exact commit if you need a full revert.)

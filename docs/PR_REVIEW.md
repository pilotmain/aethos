# Automated GitHub PR reviews

Nexa can react to GitHub `pull_request` webhooks (and manual API calls), fetch the PR diff, run static checks (Python / JS / security heuristics), optionally add LLM notes when `USE_REAL_LLM=true`, and submit a GitHub pull request review (approve when configured and clean; otherwise comment or request changes).

## Enable

In `.env`:

```bash
NEXA_PR_REVIEW_ENABLED=true
GITHUB_TOKEN=ghp_xxx          # repo scope: contents + pull requests (write for reviews)

# Optional — verify webhook payloads (recommended in production)
NEXA_PR_REVIEW_WEBHOOK_SECRET=your_secret

# Optional
NEXA_PR_REVIEW_AUTO_APPROVE=false   # if true and zero findings → APPROVE
NEXA_PR_REVIEW_MAX_FILES=50
NEXA_PR_REVIEW_IGNORE_PATTERNS=*.md,*.txt,*.lock,package-lock.json,yarn.lock,*.min.js
```

Restart the API after changing env vars.

## HTTP endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/pr-review/webhook` | GitHub webhook (`pull_request`: opened, synchronize, ready_for_review) |
| `POST` | `/api/v1/pr-review/review/{owner}/{repo}/{pr_number}` | Trigger the same pipeline manually |

When `NEXA_PR_REVIEW_WEBHOOK_SECRET` is set, GitHub must send header `X-Hub-Signature-256: sha256=<hmac_hex>` where the HMAC key is the secret and the message is the raw POST body.

## GitHub App / webhook setup

1. Repository → Settings → Webhooks → Add webhook (or org-level).
2. Payload URL: `https://<your-host>/api/v1/pr-review/webhook`
3. Content type: `application/json`
4. Events: **Pull requests** (or let GitHub send individual events for `pull_request`).
5. Secret: match `NEXA_PR_REVIEW_WEBHOOK_SECRET`.

## CLI

From the repo root (with `.venv` active):

```bash
python -m nexa_cli pr review owner/repo 42
```

Requires `NEXA_PR_REVIEW_ENABLED=true` and `GITHUB_TOKEN`.

## Behavior summary

- Files matching ignore patterns are skipped (including large globs such as `*.md`).
- Very large per-file diffs (`changes` > 500) get a warning suggestion only.
- Static rules flag likely issues (e.g. bare `except`, `eval`, suspicious assignments).
- When `USE_REAL_LLM=true`, an optional short LLM paragraph is appended as informational context (not posted as inline comments).
- If `NEXA_PR_REVIEW_AUTO_APPROVE=true` **and** there are zero findings, Nexa submits an **APPROVE** review.
- Otherwise Nexa submits **REQUEST_CHANGES** if any **error**-severity finding exists, else **COMMENT**, including inline comments on specific lines when applicable.

## Polling

`NEXA_PR_REVIEW_POLL_INTERVAL` is reserved for a future optional poller; today reviews are driven by webhooks or the manual endpoint.

# Browser automation (Phase 14)

**Stack:** Playwright async API → Chromium (CDP-style control). Execution stays **in the API process** (shared singleton browser session).

## Configuration

| Variable | Purpose |
| -------- | ------- |
| `NEXA_BROWSER_ENABLED` | Master switch (default `true`). |
| `NEXA_BROWSER_HEADLESS` | Run Chromium headless (default `true`). |
| `NEXA_BROWSER_TIMEOUT` | Default page timeout in **milliseconds** (default `30000`). |
| `NEXA_BROWSER_SCREENSHOT_DIR` | PNG/PDF output directory (default `~/Desktop`; Docker: `/app/data/screenshots`). |

Legacy: `NEXA_BROWSER_AUTOMATION_ENABLED=true` also enables the shared session (compat with Phase 41 naming).

## REST API

All routes are under `{API_V1_PREFIX}/browser` (e.g. `/api/v1/browser/...`).

**Authentication:** same Bearer token as Phase 13 cron — `Authorization: Bearer $NEXA_CRON_API_TOKEN`.

| Method | Path | Body / query |
| ------ | ---- | ------------- |
| POST | `/browser/navigate` | `{"url":"https://…","wait_until":"domcontentloaded"}` |
| POST | `/browser/click` | `{"selector":"css…"}` |
| POST | `/browser/fill` | `{"selector":"…","value":"…"}` |
| POST | `/browser/text` | `{"selector":"…"}` |
| POST | `/browser/html` | `{"selector": null \| "…"}` |
| POST | `/browser/evaluate` | `{"script":"document.title"}` |
| GET | `/browser/screenshot` | optional `?name=file.png` |
| GET | `/browser/screenshot/base64` | — |
| POST | `/browser/skill` | `{"skill_name":"browser_navigate","input":{"url":"…"}}` |

## Plugin skills

Registered at API startup from `app/services/skills/builtin_plugins/*/skill.yaml`:

- `browser_navigate`, `browser_click`, `browser_fill`, `browser_get_text`, `browser_get_html`, `browser_screenshot`, `browser_evaluate`

Host executor action:

```json
{
  "host_action": "plugin_skill",
  "skill_name": "browser_navigate",
  "input": { "url": "https://example.com" }
}
```

Chains may include `plugin_skill` steps (e.g. navigate then screenshot) when `NEXA_HOST_EXECUTOR_CHAIN_ENABLED=true`.

## Chat commands

- **Telegram:** `/browser …` (see bot help when sending `/browser` alone).
- **Slack:** `/nexa_browser …` (register the slash command in your Slack app; same text after the command as Telegram).

Both call the HTTP API above using `NEXA_CRON_API_TOKEN`, so the bot process does **not** launch its own Chromium.

## Docker

The image runs `playwright install chromium --with-deps` after `pip install`. Compose mounts `./data/screenshots:/app/data/screenshots` on the **api** service and sets `NEXA_BROWSER_SCREENSHOT_DIR=/app/data/screenshots`.

## Local development (host OS)

After `pip install -r requirements.txt`, install Chromium once:

```bash
playwright install chromium
```

On Linux CI/Docker, prefer `--with-deps` as in the Dockerfile.

## Natural language

When host executor + browser flags allow it, plain chat text can infer `plugin_skill` or a short chain (e.g. “go to https://example.com and take a screenshot”). See `try_infer_browser_automation_nl` in `app/services/host_executor_nl_chain.py`.

## Relation to Phase 41 preview

`app/services/system_access/browser_playwright.py` remains the **sync**, URL-allowlisted preview pipeline. Phase 14 adds a **persistent async session** for skills, cron, and privileged API/chat flows gated by permissions.

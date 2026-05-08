# Phase 71 — Community Skill Marketplace surfaces

## Problem

The Phase 17 ClawHub backend (`app/services/skills/{clawhub_client,clawhub_models,installer}.py`, `app/api/routes/clawhub.py`, `app/cli/clawhub.py`, `tests/test_clawhub.py`) shipped the full ClawHub-compatible install / update / remove pipeline against `installed.yaml` and the plugin registry. It was, however, only reachable via the cron-token-gated REST endpoints (`Authorization: Bearer <NEXA_CRON_API_TOKEN>`) and the `nexa_cli clawhub …` argparse subcommand.

Phase 71 fills the user-facing gap: a **Mission Control "Marketplace"** web panel, a Telegram `/skills_*` command family, and a parallel web-auth API so the browser can talk to the same installer without sharing the cron token.

## Adapted scope

The Phase 71 spec proposed re-implementing pieces that already existed (settings, models, client, installer, API). To avoid regressions and keep the manifest format / publisher trust / signature gate in one place, this phase is purely a **surface layer** on top of Phase 17:

| Spec said | What landed | Why |
|-----------|-------------|-----|
| Add `nexa_clawhub_*` settings + env vars | _Already exists_ — only added Phase 71 panel kill switch `nexa_marketplace_panel_enabled`. | Avoid duplicate / conflicting defaults. |
| New `clawhub_models.py`, `clawhub_client.py`, `installer.py` | Reused existing implementations as-is. | Same trust gates (trusted publishers, signature flag, `installed.yaml`) for cron, web, CLI, Telegram. |
| New `app/api/routes/clawhub.py` with cron-token gating | _Already exists_ — added a parallel `app/api/routes/marketplace.py` with web-auth + owner gating. | Browsers don't have `NEXA_CRON_API_TOKEN`; cron automations don't have web-user identities. |
| `aethos_cli/clawhub.py` (Click) | _Already exists_ as `app/cli/clawhub.py` (argparse) wired through `aethos_cli/__main__.py`. | Match repo CLI conventions (argparse, `clawhub_dispatch`). |
| `useAuth` web client + raw `fetch` | Used the existing `apiFetch` (wraps `webFetch` / `readConfig`). | Existing client already handles `X-User-Id`, base URL, and the optional `NEXA_WEB_API_TOKEN` bearer. |

## What landed

1. **Settings + env**
   - `app/core/config.py`: new `nexa_marketplace_panel_enabled: bool = True`.
   - `.env.example` + `.env`: matching `NEXA_MARKETPLACE_PANEL_ENABLED=true` entries (per `env-vars-sync` rules).

2. **Web-auth API proxy** — `app/api/routes/marketplace.py`
   - `GET  /api/v1/marketplace/search?q=&limit=` — read, web user.
   - `GET  /api/v1/marketplace/popular?limit=` — read, web user.
   - `GET  /api/v1/marketplace/skill/{name}` — read, web user.
   - `GET  /api/v1/marketplace/installed` — read, web user.
   - `POST /api/v1/marketplace/install` (`{name, version, force?}`) — **owner only**.
   - `POST /api/v1/marketplace/uninstall/{name}` — **owner only**.
   - `POST /api/v1/marketplace/update/{name}?force=` — **owner only**.
   - All endpoints return HTTP 503 when `nexa_marketplace_panel_enabled=False`.
   - Mutating endpoints return HTTP 403 when `get_telegram_role_for_app_user(...)` is not `owner`.
   - Wired in `app/main.py` next to the Phase 70 approvals router.

3. **Web Mission Control panel**
   - `web/lib/api/marketplace.ts`: typed client (`searchSkills`, `popularSkills`, `getSkillInfo`, `listInstalledSkills`, `installSkill`, `uninstallSkill`, `updateSkill`).
   - `web/app/mission-control/(shell)/marketplace/page.tsx`: search bar, installed-skills list with **Uninstall** / **Check for update**, popular-skills list, install buttons that disable when the skill is already installed, inline error rows mapped to backend status codes.
   - `web/lib/navigation.ts`: new "Marketplace" sidebar item with `Package` icon between **Approvals** and **Advanced**.

4. **Telegram commands** — `app/bot/clawhub_commands.py`
   - `/skills_search <query>` — top 10 results.
   - `/skills_popular` — top 10 popular.
   - `/skills_list` — installed marketplace skills.
   - `/skills_install <name> [version]` — owner only.
   - `/skills_uninstall <name>` — owner only.
   - `/skills_update <name>` — owner only.
   - All gated by `NEXA_CLAWHUB_ENABLED`; mutations additionally require Telegram `owner` role.
   - Wired in `app/services/channel_gateway/telegram_adapter.py` next to the Phase 28 budget commands.

5. **Tests** — `tests/test_marketplace_api_phase71.py` (16 cases)
   - Search / popular / installed proxy through to `ClawHubClient` and `SkillInstaller`.
   - `GET /skill/{name}` returns 404 when the registry returns nothing.
   - Install / uninstall / update return 403 for non-owners and call into the installer for owners.
   - `install` translates known installer error strings (`publisher_not_trusted`, etc.) to the right HTTP statuses.
   - Update endpoint propagates the `force` query flag.
   - Disabled flag returns 503 on every read endpoint.

6. **Docs** — appended Phase 71 sections (panel kill switch, web API table, Telegram command table, web panel description, owner-gate safety note) to `docs/CLAWHUB_MARKETPLACE.md`.

## Configuration

| Env | Default | Effect |
|-----|---------|--------|
| `NEXA_MARKETPLACE_PANEL_ENABLED` | `true` | Disable the web Marketplace panel + `/api/v1/marketplace/*` proxy with HTTP 503, without touching the Phase 17 cron-driven `/api/v1/clawhub/*` surface. |

The Phase 17 settings (`NEXA_CLAWHUB_ENABLED`, `NEXA_CLAWHUB_TRUSTED_PUBLISHERS`, `NEXA_CLAWHUB_REQUIRE_SIGNATURE`, `NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL`, …) still apply to **every** surface — cron API, CLI, Telegram, web — because they all delegate to `SkillInstaller` and `ClawHubClient`.

## What was intentionally deferred

- **Background `NEXA_CLAWHUB_AUTO_UPDATE` polling**: the flag is still reserved for a future scheduler. Phase 71 only added on-demand updates.
- **Cryptographic signature verification**: still metadata-only in v1 (gate by presence of `signature` when `NEXA_CLAWHUB_REQUIRE_SIGNATURE=true`).
- **Search filters in the UI** beyond a free-text query: tag chips and publisher filters are good follow-ups but not in this phase.
- **Per-skill detail page**: the panel surfaces inline rows; a dedicated `/marketplace/{name}` page can come when manifests start exposing screenshots / readme.

## Files touched / added

```
app/core/config.py
app/main.py
app/api/routes/marketplace.py                       # new
app/bot/clawhub_commands.py                         # new
app/services/channel_gateway/telegram_adapter.py
.env
.env.example
web/lib/navigation.ts
web/lib/api/marketplace.ts                          # new
web/app/mission-control/(shell)/marketplace/page.tsx# new
tests/test_marketplace_api_phase71.py               # new
docs/CLAWHUB_MARKETPLACE.md
docs/PHASE71_MARKETPLACE_SURFACES.md                # new
```

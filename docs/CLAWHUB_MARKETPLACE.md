# ClawHub marketplace (Phase 17, Phase 71)

Install, update, and remove **plugin skills** from a remote ClawHub-compatible registry. Coexists with Phase 6 pluggable skills (`docs/SKILLS_SYSTEM.md`) and stores disk state under `NEXA_CLAWHUB_SKILL_ROOT` (default `data/skills/`).

> **Phase 71** added the user-facing surfaces on top of the Phase 17 backend: a Mission Control **Marketplace** panel (web), a `/skills_*` family of Telegram commands, and a parallel web-auth API at `/api/v1/marketplace/*` so the browser doesn't need the cron-only token. The underlying client / installer / `installed.yaml` manifest are unchanged.

## Configuration

| Env | Default | Purpose |
|-----|---------|---------|
| `NEXA_CLAWHUB_ENABLED` | `true` | Disable all remote calls when `false`. |
| `NEXA_CLAWHUB_API_BASE` | `https://clawhub.com/api/v1` | Registry base URL (same as Phase 6). |
| `NEXA_CLAWHUB_SKILL_ROOT` | `<repo>/data/skills` | Extracted packages + `installed.yaml` manifest. |
| `NEXA_CLAWHUB_TRUSTED_PUBLISHERS` | _(empty)_ | Comma list (case-insensitive). Empty = **no** publisher filter. Non-empty = installs allowed only from listed publishers. |
| `NEXA_CLAWHUB_REQUIRE_SIGNATURE` | `false` | When `true`, reject installs whose catalog metadata has no `signature`. |
| `NEXA_CLAWHUB_AUTO_UPDATE` | `false` | Reserved for future background refresh (not wired in v1). |
| `NEXA_CLAWHUB_REQUIRE_INSTALL_APPROVAL` | `false` | When `true`, HTTP install refuses unless callers pass installer **`force`** (CLI: `--force`). |
| `NEXA_MARKETPLACE_PANEL_ENABLED` | `true` | Phase 71 — kill switch for the Mission Control Marketplace web panel + `/api/v1/marketplace/*` proxy. Set to `false` to disable browser access without disabling the cron automation surface. |

The Phase 17 cron-token surface and the Phase 71 web-auth surface are independent kill switches:

- Setting `NEXA_CRON_API_TOKEN=` disables `/api/v1/clawhub/*` (HTTP 503) but the web Marketplace panel still works.
- Setting `NEXA_MARKETPLACE_PANEL_ENABLED=false` disables the web Marketplace panel + `/api/v1/marketplace/*` (HTTP 503) but cron-driven `/api/v1/clawhub/*` automations still work.
- Setting `NEXA_CLAWHUB_ENABLED=false` disables both (the underlying client returns empty results for every call).

## REST APIs

### Cron automation — `/api/v1/clawhub` (Phase 17)

`Authorization: Bearer <NEXA_CRON_API_TOKEN>` (same gate as `POST /api/v1/cron/*`). Unset token → HTTP 503.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search?q=&limit=` | Search catalog. |
| GET | `/popular?limit=` | Popular skills. |
| GET | `/skill/{name}` | Metadata for one skill. |
| POST | `/install` | JSON `{ "name", "version": "latest" }`. |
| POST | `/uninstall/{name}` | Remove from disk, registry, manifest. |
| POST | `/update/{name}` | Re-fetch latest metadata and reinstall if newer. |
| GET | `/installed` | Local manifest entries. |

### Web panel — `/api/v1/marketplace` (Phase 71)

Standard web auth (`X-User-Id` plus optional `Authorization: Bearer <NEXA_WEB_API_TOKEN>` when configured). Mutating endpoints additionally require the **Telegram-linked owner** role (same gate the rest of the destructive web surface uses). Disabled with HTTP 503 when `NEXA_MARKETPLACE_PANEL_ENABLED=false`.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/search?q=&limit=` | web user | Search catalog. |
| GET | `/popular?limit=` | web user | Popular skills. |
| GET | `/skill/{name}` | web user | Metadata for one skill. |
| GET | `/installed` | web user | Local manifest entries. |
| POST | `/install` | **owner** | JSON `{ "name", "version": "latest", "force": false }`. |
| POST | `/uninstall/{name}` | **owner** | Remove from disk + plugin registry + manifest. |
| POST | `/update/{name}?force=` | **owner** | Re-fetch + reinstall if newer. |

The web client lives at `web/lib/api/marketplace.ts` and the page at `/mission-control/marketplace`.

## CLI

```bash
python -m nexa_cli --user-id web_dev clawhub search "git" --limit 10
python -m nexa_cli clawhub popular
python -m nexa_cli clawhub install my_skill --version latest
python -m nexa_cli clawhub list-installed
python -m nexa_cli clawhub uninstall my_skill
python -m nexa_cli clawhub update my_skill
```

## Telegram (Phase 71)

Mutating commands require the workspace **owner** role; everything else is open to any non-blocked Telegram user.

| Command | Owner only? | Description |
|---------|-------------|-------------|
| `/skills_search <query>` | no | Search the configured ClawHub registry (top 10). |
| `/skills_popular` | no | List popular skills (top 10). |
| `/skills_list` | no | List installed marketplace skills. |
| `/skills_install <name> [version]` | **yes** | Install a skill (default `version=latest`). |
| `/skills_uninstall <name>` | **yes** | Remove an installed skill. |
| `/skills_update <name>` | **yes** | Re-fetch and reinstall if a newer version exists. |

## Web Marketplace panel (Phase 71)

`Mission Control → Marketplace`:

- Search bar (proxies `GET /api/v1/marketplace/search`).
- Installed-skills section with **Uninstall** / **Check for update** per row (owner only — non-owners get HTTP 403 from the proxy).
- "Popular on ClawHub" section, refreshable.
- Install button on every search / popular result. Already-installed skills show an `installed` badge and disable the button.
- Errors from the underlying installer (`publisher_not_trusted`, `signature_required_missing`, `already_installed`, `clawhub_disabled`, `remote_metadata_unavailable`, `download_failed`) surface inline on the row.

## Docker

`docker-compose.yml` bind-mounts `./data/skills` → `/app/data/skills` for the API container so installs survive restarts.

## Safety notes

- **Trusted publishers** narrow who may be installed when the allowlist is non-empty.
- **Signature requirement** is metadata-only in v1 (no cryptographic verification unless extended later).
- **Egress**: registry host should appear in `NEXA_NETWORK_ALLOWED_HOSTS` when egress allowlists are enforced.
- **Owner gate** on the Phase 71 web/Telegram surfaces means a guest web user can browse and inspect remote skills, but cannot install code that gets registered into the plugin registry.

## Phase 75 — Marketplace polish

Phase 75 layered the production-grade UX on top of the Phase 17 + Phase 71 backend without rewriting either: it added cross-skill dependency resolution, a per-skill execution sandbox (timeout + permission allowlist), a periodic update checker that's strictly *notify-only*, a `Featured` row, category filter chips, and a skill-detail modal with README / changelog / dependencies / permissions. Docker-level isolation and a true blocking approval prompt for `network` / `filesystem_write` permissions are intentionally **deferred** (see "Out of scope" below).

### New configuration

| Env | Default | Purpose |
|-----|---------|---------|
| `NEXA_MARKETPLACE_AUTO_UPDATE_SKILLS` | `false` | Master switch for the periodic update checker. **Notify-only even when true** in v1: stamps `available_version` + emits an event but never silently re-installs. |
| `NEXA_MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS` | `86400` (1 day) | How often the in-process checker probes the registry. `0` disables the periodic loop entirely (manual `/-/check-updates-now` still works). |
| `NEXA_MARKETPLACE_SANDBOX_MODE` | `true` | When `true`, the executor enforces both the per-skill timeout and the permission allowlist. `false` restores the legacy unbounded behavior (back-compat for trusted built-in handlers). |
| `NEXA_MARKETPLACE_SKILL_TIMEOUT_SECONDS` | `30` | Max wall-clock seconds a single skill execution may run before `asyncio.wait_for` reports `timeout_exceeded`. Synchronous handlers run in `asyncio.to_thread` so the same gate applies. |
| `NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST` | _(empty — strict deny)_ | Comma-separated list of permissions a skill may request and still execute under sandbox mode. Common values: `network,filesystem_write,filesystem_read,subprocess`. Empty is the safe default — any skill that declares non-empty `permissions` will be denied at execute-time with a structured error. |
| `NEXA_MARKETPLACE_FEATURED_PANEL_ENABLED` | `true` | Hide the "Featured" row entirely in the Mission Control UI. The endpoint still answers (presentation-only toggle). |

### Failure modes

| Symptom | Likely cause | Resolution |
|---------|--------------|------------|
| Install fails with `skill_dependency_failed:missing:foo` | The remote skill declares `skill_dependencies: [foo]` but `foo` is not in the registry. | Confirm `foo` exists at `NEXA_CLAWHUB_API_BASE/skills/foo`; install it manually first or remove the dependency upstream. |
| Install fails with `skill_dependency_failed:cycle:x` | Two or more skills depend on each other (`x → y → x`). | Restructure the upstream package graph; the resolver refuses to install partially. |
| Install fails with `skill_dependency_failed:install_failed:download_failed:y` | A leaf installed cleanly but `y` couldn't be downloaded. | Re-try the install (idempotent); already-installed leaves stay installed. |
| Skill exits with `timeout_exceeded:30s` | The handler exceeded `NEXA_MARKETPLACE_SKILL_TIMEOUT_SECONDS`. | Either shorten the handler (preferred), raise the env, or run it under `NEXA_MARKETPLACE_SANDBOX_MODE=false` for trusted code. |
| Skill exits with `permission_not_allowed: …` | `manifest.permissions` are not a subset of `NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST`. | Add the requested permission (e.g. `network`) to the allowlist explicitly. The error string lists the blocked entries. |
| `/featured` row is empty | Upstream registry doesn't expose `/skills/featured` (or returned 404). | Expected for non-ClawHub registries; the UI hides the row when empty. |
| `update_check_interval_seconds=0` and Marketplace shows no update badges | Periodic loop is disabled by config. | Trigger `POST /api/v1/marketplace/-/check-updates-now` (owner-gated) or `POST /api/v1/clawhub/-/check-updates-now` (cron-token) on demand. |
| Old `installed.yaml` rows missing `category` / `available_version` | Manifest written before Phase 75. | Round-trip is automatic — re-saving any row (install / uninstall / update / `mark_update_checked`) rewrites with the new fields. |

### Cross-skill dependency model

Phase 17 already pipes `manifest.dependencies` to `pip install` for Python package dependencies — that semantics is **unchanged**. Phase 75 adds a *separate* `skill_dependencies: list[str]` field on both:

- the local `SkillManifest` (in `app/services/skills/loader.py`)
- the remote `ClawHubSkillInfo` (parsed from `data["skill_dependencies"]`)

When `SkillInstaller.install()` sees a non-empty `skill_dependencies` on the remote record, it walks the graph leaves-first via `SkillDependencyResolver`, installing every missing skill before touching the head. Already-installed skills short-circuit. Cycles raise `SkillDependencyError("cycle")`. Missing remote metadata raises `SkillDependencyError("missing", name=…)`. The head skill is **not** installed by the resolver — only its dependencies; the existing installer keeps ownership of the head (so retries / approvals / signatures stay in one place).

### Sandbox model (v1)

Two layers run *before* `execute_python_skill` actually loads the module:

1. **Permission allowlist** — `executor.assert_permissions_allowed(manifest)` checks that every entry in `manifest.permissions` is in `NEXA_MARKETPLACE_SKILL_PERMISSIONS_ALLOWLIST`. The first miss is reported in the deny string.
2. **Timeout** — the handler invocation is wrapped in `asyncio.wait_for(timeout=NEXA_MARKETPLACE_SKILL_TIMEOUT_SECONDS)`. Sync handlers are pushed onto `asyncio.to_thread` so the same gate applies.

When `NEXA_MARKETPLACE_SANDBOX_MODE=false` both layers no-op, restoring the legacy behavior.

**Out of scope (deferred, intentionally):**

- **Docker / firejail isolation** — adds a hard daemon dependency and breaks the dev box; the timeout-plus-permission gate is the lighter cousin that ships in v1.
- **Blocking approval prompt** — `host_executor.execute_payload` is a synchronous entrypoint, so a true Phase-70-style approval (`AgentJob.kind=skill_execute` + async wait) would require a new approval queue + a new path in the executor. v1 ships the strict-deny allowlist so the operator can opt in via env; a future phase can layer the prompt on top.
- **Auto-apply updates** — even with `NEXA_MARKETPLACE_AUTO_UPDATE_SKILLS=true` the checker is notify-only. Hot-reloading a running skill is unsafe; v1 requires the operator to click "Update".

### New endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| `GET`  | `/api/v1/marketplace/-/capabilities` | web | Snapshot of toggles (sandbox, timeout, allowlist, auto-update, featured). The UI renders this as a banner. |
| `GET`  | `/api/v1/marketplace/featured?limit=` | web | Curated row. Returns `{panel_enabled, skills}`. Defensive on 404. |
| `GET`  | `/api/v1/marketplace/categories` | web | De-duped list of categories observed across `/popular` ∪ `/featured`. |
| `GET`  | `/api/v1/marketplace/search?q=&category=` | web | Phase 75 added the optional `category` query param. |
| `GET`  | `/api/v1/marketplace/skill/{name}/details` | web | Reshaped payload for the detail modal: `{skill, documentation, dependencies, permissions}`. README / changelog bodies are NOT fetched server-side — only the URLs. |
| `POST` | `/api/v1/marketplace/-/check-updates-now` | web (owner) | Trigger an immediate `SkillUpdateChecker.scan_once`. Notify-only — never installs. Returns counters: `{scanned, up_to_date, updates_found, unreachable, skipped}`. |
| `GET`  | `/api/v1/clawhub/featured?limit=` | cron | Cron-token mirror of the marketplace `/featured` endpoint. |
| `GET`  | `/api/v1/clawhub/skill/{name}/details` | cron | Cron-token mirror of `/skill/{name}/details`. |
| `POST` | `/api/v1/clawhub/-/check-updates-now` | cron | Cron-token mirror — lets a scheduled job sweep the catalogue without going through the owner gate. |

### Background update checker

`app.services.skills.update_checker.SkillUpdateChecker` is a single in-process asyncio task started from the FastAPI `lifespan` context. It runs every `NEXA_MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS` (or on `kick_now`), probes every installed `SkillSource.CLAWHUB` row via `ClawHubClient.get_skill_info`, and calls `SkillInstaller.mark_update_checked` to stamp `available_version` + flip the row's status to `OUTDATED` when a newer version exists. Non-clawhub rows (LOCAL / BUILTIN) are skipped without a network call. Failures are swallowed per-skill so a single 500 from the registry doesn't break the loop for the rest of the catalogue.

The lifecycle gates short-circuit cleanly:

- `NEXA_CLAWHUB_ENABLED=false` → the loop never starts.
- `NEXA_MARKETPLACE_PANEL_ENABLED=false` → the loop never starts (matches the marketplace router gate).
- `NEXA_MARKETPLACE_UPDATE_CHECK_INTERVAL_SECONDS=0` → no periodic loop (manual probe via `POST /-/check-updates-now` still works).

### Web UI changes

- **Capabilities banner** at the top of the page renders the sandbox toggle, timeout, allowlist, and auto-update mode as colored badges. A "Check updates now" button calls `POST /-/check-updates-now` and displays the resulting counters as a transient flash.
- **Category chips** — derived from `/categories`. Selecting one re-runs `searchSkills(q || category, 25, category)`.
- **Featured row** — rendered only when `featured.panel_enabled && featured.skills.length > 0`.
- **Update available badge** — installed cards now show `update → 1.1.0` (yellow `warning` variant) when the checker has stamped a newer `available_version`. The "Check for update" button becomes a primary "Update to 1.1.0" CTA.
- **SkillDetailModal** — opens on remote-card click or the "Details" button. Renders the long description, the dependency graph (as outline badges), the requested permissions (with a `(denied)` annotation when they exceed the operator allowlist), and links to README / changelog / manifest. The install button mirrors the card-level state.


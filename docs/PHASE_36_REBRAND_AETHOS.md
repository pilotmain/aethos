# Phase 36 — Rebrand Nexa → AethOS

**Tagline:** *The Agentic Operating System* · **Pronunciation:** “EE-thos” · **Etymology:** Aether + OS — the invisible layer that connects autonomous agents.

This document is the **canonical playbook** for humans and Cursor agents when renaming product surfaces from **Nexa** to **AethOS**. The Git repository may remain **`nexa-next`** on GitHub until the remote is renamed; URLs and clone paths are called out explicitly below.

---

## 1. What changed in code (high level)

| Area | Change |
|------|--------|
| **Product name** | Default `Settings.app_name` is **`AethOS`** → `/api/v1/health` returns `"app": "AethOS"`. |
| **Environment** | Prefer **`AETHOS_*`** keys. **`app/core/aethos_env.py`** mirrors each `AETHOS_<SUFFIX>` → `NEXA_<SUFFIX>` **before** `Settings()` loads so existing Python fields (`nexa_*`) keep working. **AETHOS wins** when both are set. |
| **CLI package** | Directory **`nexa_cli/`** → **`aethos_cli/`**. Entry points: **`aethos`** (primary) and **`nexa`** (compatibility alias) → same `main`. |
| **Mobile** | Directory **`nexa-mobile/`** → **`aethos-mobile/`**. |
| **Web** | `web/components/nexa/` → **`web/components/aethos/`**; `web/lib/nexa-types.ts` → **`web/lib/aethos-types.ts`**; types **`NexaJob`** → **`AethosJob`**. |
| **Installer** | **`scripts/install_aethos.sh`** is canonical; **`scripts/install_nexa_next_native.sh`** exec-forwards to it. |
| **Docker Compose** | Project name **`aethos`**; images/containers **`aethos:local`**, **`aethos-api`**, etc. |
| **CI** | `.github/workflows/mobile.yml` watches **`aethos-mobile/**`**. |
| **Marketplace sample data** | **`data/nexa_marketplace/`** → **`data/aethos_marketplace/`** (backend path updated). |

---

## 2. Environment variables

### 2.1 Preferred names (`AETHOS_*`)

Use **`AETHOS_WORKSPACE_ROOT`**, **`AETHOS_AGENT_ORCHESTRATION_ENABLED`**, etc. Documented alongside legacy names in **`.env.example`**.

### 2.2 Legacy (`NEXA_*`)

All existing **`NEXA_*`** variables remain valid. At process startup, **`apply_aethos_env_aliases()`** copies **`AETHOS_*`** onto **`NEXA_*`** so `pydantic-settings` continues to populate fields named `nexa_*` without a multi-thousand-line rename.

### 2.3 Optional branded aliases

| AETHOS (preferred) | Also maps into |
|--------------------|----------------|
| `AETHOS_TELEGRAM_BOT_TOKEN` | `TELEGRAM_BOT_TOKEN` |
| `AETHOS_OPENAI_API_KEY` | `OPENAI_API_KEY` |
| `AETHOS_WEB_API_TOKEN` | `NEXA_WEB_API_TOKEN` |
| `AETHOS_API_BASE` | `NEXA_API_BASE` |

### 2.4 Migrating `.env` files

Dry-run:

```bash
python scripts/migrate_env_aethos.py --dry-run
```

Apply (creates `.env.nexa_backup`):

```bash
python scripts/migrate_env_aethos.py --write
```

---

## 3. CLI commands

| Before | After |
|--------|--------|
| `nexa serve` | **`aethos serve`** (or `nexa serve` — alias) |
| `python -m nexa_cli` | **`python -m aethos_cli`** |

After `pip install -e .`, both **`aethos`** and **`nexa`** console scripts resolve to **`aethos_cli.__main__:main`**.

---

## 4. Python codebase — intentional leftovers

Many internal symbols still contain **`nexa`** (e.g. **`NexaGateway`**, **`NexaUserSettings`**, SQL tables **`nexa_*`**). Renaming those requires coordinated DB migrations and wide import churn; Phase 36 focuses on **user-visible branding**, **CLI/mobile/web surfaces**, and **env ergonomics**. Track deeper identifier renames as a follow-up phase if desired.

---

## 5. Web browser localStorage

| Key | Notes |
|-----|--------|
| **`aethos_web_v1`** | Current config blob (API base, user id, token). |
| **`nexa_web_v1`** | Legacy — still **read** if the new key is missing. |

Public env for Next.js:

- Prefer **`NEXT_PUBLIC_AETHOS_API_BASE`**
- Legacy **`NEXT_PUBLIC_NEXA_API_BASE`** still supported in `web/lib/config.ts`.

---

## 6. Verification checklist

```bash
python -m compileall -q app aethos_cli
pip install -e .
aethos status
curl -s "${AETHOS_API_BASE:-http://127.0.0.1:8010}/api/v1/health" | python -m json.tool   # expect "app": "AethOS"
```

Optional leftover string audit (exclude repo name **nexa-next** in prose):

```bash
rg '\bNexa\b' app web aethos_cli docs --glob '!**/node_modules/**' || true
```

---

## 7. Assets (logo / favicon)

Replace **`web/public`** icons and add **`aethos-logo.svg`** when creative assets are ready. Phase 36 does not block on artwork — placeholders may remain until design lands.

---

## 8. Related paths in repo

| Path | Purpose |
|------|---------|
| `app/core/aethos_env.py` | Env mirroring |
| `scripts/migrate_env_aethos.py` | `.env` key rewrite helper |
| `scripts/install_aethos.sh` | Native installer |
| `scripts/rebrand_to_aethos.sh` | Prints verification hints |

---

## 9. Commit message template

```
feat: rebrand product surfaces to AethOS (Phase 36)

- AETHOS_* env aliases + default app_name AethOS
- Rename aethos_cli / aethos-mobile; pyproject entrypoints aethos + nexa alias
- Web/mobile branding, Mission Control metadata, marketplace data path
- Docs and installer scripts
```

---

*End of Phase 36 playbook.*

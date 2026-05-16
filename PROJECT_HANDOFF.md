# AethOS project handoff — OpenClaw parity-first doctrine

This document is the repo-local handoff for reproducing and developing the AethOS stack. The governing objective is now strict:

> **Phase 1 objective: reproduce OpenClaw exactly as it works today.**
>
> Privacy, PII filtering, local-first differentiation, cost transparency improvements, and other AethOS-specific advantages are **Phase 2** work. They must not drive Phase 1 architecture unless they are required to reproduce current OpenClaw behavior.

No contributor should optimize for novelty, differentiation, branding, or architectural preference until OpenClaw behavioral parity has been achieved and verified.

**Master implementation plan:** [docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md) — CLI + gateway command matrix (`aethos onboard`, `aethos gateway`, `aethos message send`, …), workspace layout targets (`~/.aethos/…`), required parity **test modules**, and priorities **P1–P4**.

**Parity lock, transition gate, final operational certification, and Phase 2 boundary:** [docs/OPENCLAW_FINAL_PARITY_AUDIT.md](docs/OPENCLAW_FINAL_PARITY_AUDIT.md) (suite totals, boundedness table, closure) and **[docs/PHASE1_CERTIFICATION_CLOSURE_PHASE2_BOUNDARY.md](docs/PHASE1_CERTIFICATION_CLOSURE_PHASE2_BOUNDARY.md)** (freeze declaration, allowed/forbidden changes, Phase 2 activation rules).

---

## 1. What you are reproducing

| Layer | Role in OpenClaw parity |
| --- | --- |
| `app/` | FastAPI API, gateway routes, orchestration, adapters, deployment helpers, system access, memory, autonomy, and agent runtime surfaces. |
| `web/` | Next.js Mission Control UI. During Phase 1, UI work should reproduce OpenClaw workflows before custom UX improvements. |
| `aethos_cli/` | `aethos` / `nexa` CLI surfaces for serving, HTTP helpers, and local control flows. |
| Database | SQLite by default, optional Postgres. Use the same durable state expectations needed for OpenClaw-like runs. |
| Host tools / gateway | Shell, files, browser, deploy, memory, provider routing, and channel integrations required for parity. |

Optional satellite trees such as `aethos-mobile/` and `nexa-ext-pro/` are not Phase 1 priorities unless they directly close an OpenClaw parity gap.

---

## Enterprise first impression (Phase 4 Step 11)

One-curl install is certified through `install.sh` → `scripts/setup.sh` → enterprise wizard. Verify with `aethos setup certify` or `GET /api/v1/setup/certify`. User-facing branding is **AethOS**; OpenClaw remains in parity docs/tests only. See [docs/ONE_CURL_CERTIFICATION.md](docs/ONE_CURL_CERTIFICATION.md) and [docs/MISSION_CONTROL_READY_STATE.md](docs/MISSION_CONTROL_READY_STATE.md).

## Launch readiness (Phase 4 Step 13)

`enterprise_overview.phase` is `phase4_step13` with `launch_ready` after runtime evolution. Certification: [docs/LAUNCH_READINESS_CERTIFICATION.md](docs/LAUNCH_READINESS_CERTIFICATION.md). Identity: [docs/AETHOS_LAUNCH_IDENTITY.md](docs/AETHOS_LAUNCH_IDENTITY.md).

## Release candidate (Phase 4 Step 14)

`enterprise_overview.phase` is `phase4_step14` with `release_candidate`. Certification: [docs/FINAL_RELEASE_CANDIDATE_CERTIFICATION.md](docs/FINAL_RELEASE_CANDIDATE_CERTIFICATION.md). Freeze: [docs/LAUNCH_CANDIDATE_FREEZE.md](docs/LAUNCH_CANDIDATE_FREEZE.md).

## Installer & onboarding (Phase 4 Step 15)

Conversational setup with resume continuity and Mission Control first-impression lock. APIs: `/api/v1/setup/continuity`, `/first-impression`. See [docs/FIRST_IMPRESSION_CERTIFICATION.md](docs/FIRST_IMPRESSION_CERTIFICATION.md).

## Setup finalization (Phase 4 Step 16)

Unified `aethos doctor`, seamless MC bootstrap, progressive runtime startup UI, branding/language lock. See [docs/ENTERPRISE_FIRST_IMPRESSION.md](docs/ENTERPRISE_FIRST_IMPRESSION.md).

---

## 2. Non-negotiable product rule

Every change must satisfy at least one of these:

1. Reproduces a concrete OpenClaw behavior.
2. Fixes a regression that prevents OpenClaw parity.
3. Adds test/verification coverage for OpenClaw parity.
4. Supports install/run reliability needed to evaluate parity.

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

**Phase 2 Step 7 (brain-routed repair):** See [docs/BRAIN_ROUTING.md](docs/BRAIN_ROUTING.md). Repair flows collect privacy-safe evidence, select a brain (`app/brain/`), validate structured plans, run safe in-repo edits, verify locally, then redeploy via provider actions. Mission Control exposes `brain_summary` on `latest_repair_contexts`.

**Phase 2 Step 8 (Mission Control runtime intelligence):** See [docs/MISSION_CONTROL.md](docs/MISSION_CONTROL.md), [docs/PLUGINS.md](docs/PLUGINS.md), [docs/RUNTIME_EVENTS.md](docs/RUNTIME_EVENTS.md). Dynamic `runtime_agents`, slice APIs under `/mission-control/runtime*`, Office UI at `/mission-control/office`, plugin manifests in `app/plugins/`.

**Phase 2 Step 9 (real-time MC + marketplace foundation):** Categorized runtime events, agent lifecycle (busy/idle/suspend/expire), live panels API, metrics cache, plugin load/disable APIs (`/api/v1/plugins/*`), Office topology. See [docs/RUNTIME_AGENTS.md](docs/RUNTIME_AGENTS.md), [docs/PLUGIN_MARKETPLACE.md](docs/PLUGIN_MARKETPLACE.md).

**Phase 2 Step 10 (simplification + polish):** Authoritative `runtime_truth` path, consolidated runtime health (`healthy|warning|degraded|critical`), event aggregation, plugin failure isolation, `trust_tier` on plugins, operator trace API. See [docs/RUNTIME_CLEANUP_RECON.md](docs/RUNTIME_CLEANUP_RECON.md).

**Phase 2 Step 11 (cleanup + production polish):** Cached runtime truth, lifecycle sweeps, `build_execution_snapshot` unified with truth, plugin health panel, operator trace bundles (`GET /runtime-traces`), severity-prioritized events, Office UX polish.

**Phase 3 Step 1 (ecosystem + marketplace):** Plugin install lifecycle (`~/.aethos/plugins/`), marketplace APIs (`/marketplace/plugins`, install/uninstall/upgrade), operational intelligence, brain routing panel, workspace intelligence, governance audit, automation packs, MC `/mission-control/plugins` UI. See [docs/MARKETPLACE.md](docs/MARKETPLACE.md).

**Phase 3 Step 2 (native differentiation):** Documented advantages (`docs/AETHOS_DIFFERENTIATION.md`), privacy operational posture, brain routing metadata (fallback chain, cost), differentiation APIs (`/mission-control/differentiators`, etc.), MC `/mission-control/differentiators`. See [docs/AETHOS_DIFFERENTIATION.md](docs/AETHOS_DIFFERENTIATION.md).

**Phase 3 Step 3 (MC polish + runtime cleanup):** Office operational API (`GET /mission-control/office`), agent role/persistent model, event aging, runtime discipline metrics, panel cache cohesion. See [docs/RUNTIME_SIMPLIFICATION_AUDIT.md](docs/RUNTIME_SIMPLIFICATION_AUDIT.md), [docs/ARCHITECTURE_SIMPLIFICATION.md](docs/ARCHITECTURE_SIMPLIFICATION.md).

Deferred until after verified parity:

- privacy-first redesigns
- PII filtering systems
- safety-layer redesigns
- custom orchestration experiments
- novel agent frameworks
- custom UX paradigms
- local-first-only behavior that changes OpenClaw-compatible semantics
- cost/transparency features that block or reshape parity workflows

These can remain behind flags only when they do not alter default Phase 1 behavior.

---

## 3. Phase 1 parity checkpoints

AethOS is not considered Phase 1 complete until the following are demonstrably equivalent to OpenClaw behavior:

- agent orchestration parity
- tool execution parity
- shell/workspace parity
- browser/tool-use parity
- deployment workflow parity
- Mission Control/UI parity
- memory/context parity
- autonomous workflow parity
- provider/model routing parity
- multi-agent coordination parity
- channel integration parity where OpenClaw supports comparable surfaces
- install/bootstrap parity
- regression test coverage for the reference workflows

Each checkpoint needs either automated tests, a repeatable manual test script, or an explicit documented gap.

---

## 4. Hard requirements for reproducing the stack

1. Python >= 3.10.
2. Git, because `requirements.txt` may install dependencies from GitHub.
3. Node.js + npm for `web/`.
4. Network at dependency-install time.
5. Repo-root `.env`; settings may also load `~/.aethos/.env` after the repo file, so know which value wins.
6. Port alignment: API, web, CORS, and browser connection settings must all point to the same API origin, usually port `8010`.
7. Shared database settings for API, bot/channel workers, and automation processes.

---

## 5. Canonical install

```bash
git clone https://github.com/pilotmain/aethos.git
cd aethos
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
cp .env.example .env
python -c "from app.core.db import ensure_schema; ensure_schema()"
```

If dependency installation fails on a Git dependency, fix Git/network access first.

---

## 6. Database and durable state

- Default SQLite path is expected to resolve under `~/.aethos/data/aethos.db` unless overridden.
- `AETHOS_DATA_DIR` changes the durable data directory.
- `DATABASE_URL` overrides the SQLAlchemy URL completely.
- API, Telegram, Slack/Discord workers, and scheduler/autonomy workers must share the same database URL when reproducing an integrated OpenClaw-style stack.
- `NEXA_NEXT_LOCAL_SIDECAR=1` can force a repo-local SQLite sidecar for development only.

Initialize schema:

```bash
source .venv/bin/activate
python -c "from app.core.db import ensure_schema; ensure_schema()"
# or
aethos init-db
```

---

## 7. Environment priorities for parity

Start from:

```bash
cp .env.example .env
```

Minimum values usually needed for realistic parity testing:

| Variable | Why it matters |
| --- | --- |
| `NEXA_SECRET_KEY` | Signing and app security. |
| `NEXA_WEB_API_TOKEN` | Mission Control bearer auth when enabled. |
| `NEXA_WEB_ORIGINS` | CORS for local web origins. |
| `AETHOS_OWNER_IDS` | Owner-class privileges for privileged routes. |
| `USE_REAL_LLM` | `true` for realistic provider behavior; `false` for deterministic smoke. |
| `NEXA_LLM_PROVIDER`, `NEXA_LLM_MODEL`, fallbacks | Provider/model routing parity. |
| `NEXA_LLM_FIRST_GATEWAY` | Prefer OpenClaw-like gateway behavior when reproducing conversational flows. |
| `NEXA_WORKSPACE_ROOT` / dev workspace roots | File and command execution parity. |
| `NEXA_HOST_EXECUTOR_ENABLED`, `NEXA_COMMAND_EXECUTION_ENABLED` | Shell/tool execution parity gates. |
| Deploy provider tokens / CLIs | Needed only for deployment workflow parity. |
| Channel tokens | Needed for Telegram/Slack/Discord parity checks. |

Privacy and PII variables should not become Phase 1 blockers unless the exact OpenClaw behavior being reproduced depends on them.

---

## 8. Running the stack

API:

```bash
aethos serve --host 0.0.0.0 --port 8010 --reload
# or
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

Web:

```bash
cd web
npm install
NEXT_PUBLIC_AETHOS_API_BASE=http://127.0.0.1:8010 npm run dev
```

Telegram/channel workers:

- If embedded polling is enabled, do not run a second poller.
- For separate Telegram process mode:

```bash
python -m app.bot.telegram_bot
```

---

## 9. Verification before handing to a tester

Run at minimum:

```bash
python -m compileall -q app aethos_cli
pytest
```

For parity work, also run or update:

```bash
pytest tests/test_openclaw_parity.py
pytest tests/test_openclaw_*_parity.py
pytest tests/test_openclaw_runtime_*.py
pytest tests/test_openclaw_task_*.py tests/test_openclaw_scheduler.py tests/test_openclaw_queue_*.py tests/test_openclaw_agent_runtime.py tests/test_openclaw_orchestration_recovery.py tests/test_openclaw_deployment_recovery.py tests/test_openclaw_runtime_dispatcher.py
pytest tests/test_openclaw_execution_*.py tests/test_openclaw_autonomous_execution.py
pytest tests/test_openclaw_doctrine_docs.py
```

A PR is not ready unless it states:

1. Which OpenClaw behavior it reproduces.
2. Which parity checkpoint it advances.
3. How it was verified.
4. Whether any divergence remains.

---

## 10. Documentation map

Read in this order:

1. `README.md` — install and top-level parity objective.
2. `PROJECT_HANDOFF.md` — this doctrine and reproduction guide.
3. `.env.example` — exhaustive environment catalog.
4. `docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md` — **master implementation plan** (CLI matrix, priorities P1–P4, test module matrix).
5. `docs/OPENCLAW_PARITY_AUDIT.md` — parity checkpoints and gaps.
6. `docs/MIGRATING_FROM_OPENCLAW.md` — migration framed as exact parity first.
7. `docs/SETUP.md`, `docs/installation.md`, `docs/configuration.md` — setup details.
8. `docs/WEB_UI.md` — Mission Control behavior.
9. `CONTRIBUTING.md` and `.cursor/rules/openclaw-parity-first.mdc` — contributor enforcement.

When docs and code disagree, trust code plus parity tests, then fix the docs.

---

## 11. Copy-paste checklist for a new machine

- [ ] Clone `https://github.com/pilotmain/aethos.git`.
- [ ] Create and activate `.venv`.
- [ ] Install `requirements.txt` and `pip install -e .`.
- [ ] Copy `.env.example` to `.env`.
- [ ] Set secrets, web token, owner IDs, LLM provider/model, and channel/deploy tokens needed for the parity scenario.
- [ ] Align API port, web API base, and CORS origins.
- [ ] Initialize schema.
- [ ] Start API.
- [ ] Start web.
- [ ] Start channel workers only when configured and not embedded.
- [ ] Run `python -m compileall -q app aethos_cli`, `pytest`, `pytest tests/test_openclaw_parity.py`, `pytest tests/test_openclaw_*_parity.py`, `pytest tests/test_openclaw_runtime_*.py`, `pytest tests/test_openclaw_task_*.py tests/test_openclaw_scheduler.py tests/test_openclaw_queue_*.py tests/test_openclaw_agent_runtime.py tests/test_openclaw_orchestration_recovery.py tests/test_openclaw_deployment_recovery.py tests/test_openclaw_runtime_dispatcher.py`, `pytest tests/test_openclaw_execution_*.py tests/test_openclaw_autonomous_execution.py`, and `pytest tests/test_openclaw_doctrine_docs.py`.
- [ ] Record remaining OpenClaw divergences in `docs/OPENCLAW_PARITY_AUDIT.md`.

---

## 12. Phase 2 reminder

After exact OpenClaw functional parity is verified, AethOS may resume differentiated work on privacy, PII filtering, cost transparency, local-first execution, and safer governance. Phase 2 improvements must preserve parity unless an intentional breaking change is explicitly approved.

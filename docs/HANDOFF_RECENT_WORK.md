# Handoff: recent work (install, web UI, docs)

**Full-picture view of the whole product and repo:** use [HANDOFF_PLATFORM_OVERVIEW.md](HANDOFF_PLATFORM_OVERVIEW.md) first if you need recommendations and roadmap fit.

This page is a **narrow slice** of what landed in a recent period: installer UX, web session deletion, enterprise architecture doc, GitHub org / domain alignment, and related notes. For day-to-day dev workflow, use [DEVELOPMENT_HANDOFF.md](DEVELOPMENT_HANDOFF.md) and [CURSOR_HANDOFF.md](CURSOR_HANDOFF.md).

---

## 1. One-line install (`curl | bash`)

**Goal:** Install Nexa like a CLI tool: clone, venv, `requirements.txt`, web `npm install`, `.env`, optional key prompts, `ensure_schema`, then start **Docker** (`./run_everything.sh start`) when Docker is available, otherwise **host** API + Next dev server.

| Item | Location / notes |
|------|-------------------|
| Installer script | [`scripts/install.sh`](../scripts/install.sh) — wraps [`scripts/nexa_bootstrap.py`](../scripts/nexa_bootstrap.py) / [`app/services/nexa_bootstrap.py`](../app/services/nexa_bootstrap.py) |
| Repo-root wrapper | [`install.sh`](../install.sh) → `scripts/install.sh --no-clone` |
| User-facing command | `curl -fsSL https://pilotmain.com/install.sh \| bash` |
| Canonical script URL | `https://raw.githubusercontent.com/pilotmain/nexa/main/scripts/install.sh` |
| Default clone URL in script | `https://github.com/pilotmain/nexa.git` |

**Short URL:** `https://pilotmain.com/install.sh` is **not** defined in this repo. It is an HTTP redirect configured on the **marketing site** (e.g. pilotos-site on Vercel: root `vercel.json` maps `/install.sh` → GitHub raw). After deploy, verify:

```bash
curl -fsSIL https://pilotmain.com/install.sh
curl -fsSL https://pilotmain.com/install.sh | head -5
```

**Docs:** [README.md](../README.md) (Quick start), [docs/SETUP.md](SETUP.md) (One-line install).

**Commits (examples):** `ab302044`, `d81775e8` (docs cleanup toward `pilotmain.com/install.sh`).

---

## 2. Delete chat history from the web sidebar

**Goal:** Per-session **delete** or **clear** from the left sessions list, with confirmation, without deleting the main “default” row (main session **clears** stored messages/state; other sessions **remove** the row).

| Layer | What |
|-------|------|
| API | `DELETE /api/v1/web/sessions/{session_id}` → **204**, empty body — [`app/api/routes/web.py`](../app/api/routes/web.py) |
| Service | `delete_or_clear_web_session` — non-`default` deletes row; `default` clears rollups — [`app/services/conversation_context_service.py`](../app/services/conversation_context_service.py) |
| UI | Overflow menu (⋯) per row, `window.confirm`, `webFetch` DELETE, refresh list, `switchWebSession(..., { force: true })` when clearing active main session — [`web/components/nexa/WorkspaceApp.tsx`](../web/components/nexa/WorkspaceApp.tsx) |
| Tests | [`tests/test_web_chat_sessions.py`](../tests/test_web_chat_sessions.py) |

**Larger merge:** This shipped with other web/API work in commit **`e91a6b96`** (“safety and governance stack, trust UI, web sessions, agent tasks”).

---

## 3. Enterprise / platform architecture (diagram doc)

**Added:** [`docs/VISUAL_ARCHITECTURE.md`](VISUAL_ARCHITECTURE.md) — ASCII + Mermaid diagrams for client layers, Nexa platform blocks (identity, governance, agents, permissions, execution safety, tools, audit), and runtime/deployment. Complements codebase-focused [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).

---

## 4. GitHub remote and branding

- Remote org/repo in use: **`pilotmain/nexa`** (`https://github.com/pilotmain/nexa.git`).
- Installer, README, and comments reference **pilotmain** (not legacy org names).
- **Large historical push:** `e91a6b96` bundled many files (safety policy, trust surfaces, permissions flows, `.agent_tasks` artifacts, etc.). Use `git show e91a6b96 --stat` for the full list.

---

## 5. Verification checklist (Nexa repo)

From repo root (venv optional depending on command):

```bash
python -m compileall -q app
python -m pytest tests/test_web_chat_sessions.py -q
```

After backend changes: restart **uvicorn** (and web dev server if testing UI).

---

## 6. Out of scope for this repository

| Topic | Where it lives |
|-------|------------------|
| `pilotmain.com` redirect for `/install.sh` | **pilotos-site** (or whichever project deploys the marketing domain) — `vercel.json` redirect only; **no** Nexa code change required there for redirect behavior |
| DNS / SSL for `pilotmain.com` | Hosting provider / Vercel project settings |

---

## 7. Quick file index (this thread’s themes)

| Path | Role |
|------|------|
| `scripts/install.sh` | Bootstrap orchestration |
| `install.sh` | Wrapper after clone |
| `app/api/routes/web.py` | `DELETE /web/sessions/...` |
| `app/services/conversation_context_service.py` | Delete / clear session |
| `web/components/nexa/WorkspaceApp.tsx` | Sidebar delete UX |
| `tests/test_web_chat_sessions.py` | Session API tests |
| `docs/VISUAL_ARCHITECTURE.md` | Enterprise diagram doc |
| `README.md`, `docs/SETUP.md` | Quick start & one-line install |

---

*If this doc drifts from `main`, prefer `git log` and the paths above as source of truth.*

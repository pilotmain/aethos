# Phase 73b — Self-Improvement (Genesis Loop, safe-adapt v1)

## What this phase is and is not

Phase 73 closed the loop on **self-healing** — agents detect their own
failures and recover automatically. Phase 73b closes the loop on
**self-improvement** — the same system can now propose and (after explicit
owner approval and a passing local sandbox run) apply code changes to
itself.

This is the first phase where AethOS modifies its own source. We deliberately
chose a **safe-adapt** scope rather than the literal spec, because the
literal spec ("LLM proposes a diff → push to a temp branch on GitHub → run
CI → auto-merge → graceful restart") wires AethOS into a write-capable
GitHub PAT, requires a CI pipeline that doesn't exist yet, and assumes a
production restart mechanism that doesn't exist yet. Each of those is a
separate substantial workstream and each adds new failure modes.

The 73b implementation gives us the **exact same loop** without those
risks: local `git worktree` sandbox, owner-gated apply that creates a
local commit only (no push, no restart), and an always-available revert.

## What landed

### Backend

| File | Purpose |
|---|---|
| `app/core/config.py` | Five new settings under `nexa_self_improvement_*`, plus two reserved-for-Phase-73c vars (`github_token`, `base_branch`) parsed but unused so adding the GitHub flow later is config-stable. |
| `.env.example` & `.env` | Synced — `NEXA_SELF_IMPROVEMENT_ENABLED=false` by default. |
| `app/services/self_improvement/context.py` | Read-only allowlisted file fetcher. Hard allowlist (`NEXA_SELF_IMPROVEMENT_ALLOWED_PATHS`, default `app/services/,app/api/routes/,docs/`) plus a hard denylist that always wins (`.env*`, `app/core/secrets*`, `*credentials*`, `*private_key*`, `id_rsa`, `*.pem`, `*.p12`, `*.key`, any `*.db` / `*.sqlite*`). Rejects absolute paths and `..` traversal. 64 KiB per-file size cap. |
| `app/services/self_improvement/proposal.py` | • `parse_unified_diff` — minimal hand-rolled unified-diff parser (no new deps).<br>• `validate_proposal_diff` — enforces allowlist + max files + max combined +/- lines + secret-scan over added lines + no-op + scorched-earth deletion guards.<br>• `generate_proposal_diff` — calls `primary_complete_messages(task_type="self_improvement_diff")` so Phase 72's cost-aware router picks the right model, with a system prompt that constrains the LLM to "exactly one unified diff or `# NO_DIFF_AVAILABLE`".<br>• `ProposalStore` — SQLite-backed persistence in the existing `data/agent_audit.db` (new table `self_improvement_proposals`, lazy schema). Tracks status (`pending`/`approved`/`rejected`/`applied`/`reverted`), sandbox result blob, applied/reverted commit SHAs. |
| `app/services/self_improvement/sandbox.py` | Isolated `git worktree add --detach` rooted at HEAD into `data/self_improvement_worktrees/<id>/`, then `git apply --check` → `git apply` → `python -m compileall -q app` → targeted `pytest -x -q`. Per-step subprocess timeouts. Always cleans up worktree (`git worktree remove --force` + rmtree + `git worktree prune`). Returns a structured `SandboxResult`; never raises. |
| `app/api/routes/self_improvement.py` | HTTP surface under `/api/v1/self_improvement/`. Read endpoints (`GET /`, `GET /{id}`) require web auth; mutating endpoints (`/propose`, `/{id}/sandbox`, `/{id}/approve`, `/{id}/reject`, `/{id}/apply`, `/{id}/revert`) additionally require the Telegram-linked owner. The whole router 404s when `NEXA_SELF_IMPROVEMENT_ENABLED=false` (so it stays dark for snoops); `/{id}/revert` is the one exception that's always available so an operator can always undo. |
| `app/main.py` | Includes `self_improvement.router` under the `api_v1_prefix`. |

### Web

| File | Purpose |
|---|---|
| `web/lib/api/self_improvement.ts` | Typed client. |
| `web/lib/navigation.ts` | "Improvements" sidebar entry pointing at `/mission-control/self-improvement` (the URL slug deliberately starts with `/self-` to stay clear of the Phase 48 identity-lock blocked substring `/improve`). |
| `web/app/mission-control/(shell)/self-improvement/page.tsx` | Mission Control page: propose form (title / problem statement / target paths / extra context / rationale), validation summary inline, proposals list with status badges + sandbox pass/fail badge, expandable unified-diff viewer with `+`/`-`/hunk-header coloring, per-row Sandbox / Approve / Reject / Apply / Revert buttons gated by status, inline status banner with `ok`/`warn`/`err` tones. |

### Tests

`tests/test_self_improvement_phase73b.py` — **27 cases**, all green:

* `context` — allowlist accepts allowed paths; denylist rejects `.env*`,
  `app/core/secrets*`, credentials/private-key/db patterns, paths outside
  the allowlist, traversal, absolute paths. End-to-end fetch reads a real
  file. Disallowed fetches raise `ContextNotAllowedError`.
* `validate_proposal_diff` — empty, no-headers, happy path, path outside
  allowlist, secret pattern in added line, too-many-files, scorched-earth
  pure-deletion.
* `ProposalStore` — create/get/list, status transitions, sandbox-result
  persistence + freshness query.
* `generate_proposal_diff` — wires `task_type="self_improvement_diff"`
  through to `primary_complete_messages`, rejects disallowed targets up
  front (so the LLM never sees forbidden paths in the prompt), strips
  Markdown fences from the LLM response.
* `run_sandbox` — happy path (compileall + pytest both green via mocked
  subprocess), `git apply --check` failure returns `diff_does_not_apply_cleanly`,
  worktree-create failure returns `worktree_create_failed`. Always cleans
  up regardless of outcome.
* API — `404` when `NEXA_SELF_IMPROVEMENT_ENABLED=false`, `403` for
  non-owner on `/propose`, `200` happy path persists with mocked LLM,
  `/apply` returns `412` without a fresh passing sandbox run, `/revert`
  returns `409` when not in `applied` state, `/{id}` returns `404` for
  unknown id, `/` lists newest first.

## Configuration matrix

```bash
# Phase 73b master switch (default off — feature is dark until you opt in).
NEXA_SELF_IMPROVEMENT_ENABLED=false

# Per-proposal caps. Both are enforced by validate_proposal_diff and
# returned as structured errors when violated.
NEXA_SELF_IMPROVEMENT_MAX_FILES_PER_PROPOSAL=5
NEXA_SELF_IMPROVEMENT_MAX_DIFF_LINES=400          # combined +/-

# Sandbox per-subprocess wall-clock cap (seconds).
NEXA_SELF_IMPROVEMENT_SANDBOX_TIMEOUT_S=120

# Comma-separated path prefixes that proposals may touch. Default is
# narrow on purpose — widen via env when you want to let the loop touch
# new surfaces (e.g., add ``web/app/`` once you trust a few proposals).
NEXA_SELF_IMPROVEMENT_ALLOWED_PATHS=app/services/,app/api/routes/,docs/

# Reserved for Phase 73c. Parsed but unused in 73b (added now so the
# config schema stays stable across the next phase bump).
NEXA_SELF_IMPROVEMENT_GITHUB_TOKEN=
NEXA_SELF_IMPROVEMENT_BASE_BRANCH=main
```

## End-to-end flow (operator's POV)

1. **Owner** opens Mission Control → Improvements, fills in title +
   problem statement + target paths, clicks "Generate proposal".
2. The API calls `generate_proposal_diff` → `primary_complete_messages`
   with `task_type="self_improvement_diff"` and a strict system prompt.
   The returned diff goes through `validate_proposal_diff` before
   anything is persisted; failures surface inline with structured errors
   and a 4 KiB diff preview, so the operator can see what the LLM
   produced and tweak the prompt.
3. On a clean validation, the proposal lands in
   `self_improvement_proposals` with status `pending`. The operator
   reviews the diff in the UI's expandable viewer (with `+`/`-` coloring).
4. Operator clicks **Sandbox** — `run_sandbox` creates a `git worktree` at
   HEAD, applies the diff there, runs `compileall app`, then targeted
   `pytest -x -q` against tests inferred from the diff's modified files
   (`app/services/foo.py` → `tests/test_foo*.py`). The worktree is
   removed regardless of outcome. The sandbox result is persisted on the
   proposal row so the UI can show "sandbox: pass / fail" without
   re-running.
5. Operator clicks **Approve** (status flips `pending` → `approved`).
6. Operator clicks **Apply** — only allowed if (a) status == `approved`,
   (b) the persisted sandbox result is `success: True`, and (c) the
   sandbox ran less than 60 seconds ago. The diff is applied to the
   working copy with `git apply`, only the touched files are staged, and
   a single commit is created with message `[self-improvement:<id>] <title>`.
   **No push, no restart.** The commit SHA is stored on the proposal row
   and surfaced in the UI.
7. Operator pushes (or doesn't) and restarts the API on their schedule.
8. If the change misbehaves, **Revert** is always available (regardless
   of `NEXA_SELF_IMPROVEMENT_ENABLED`): `git revert --no-edit <sha>`
   creates a follow-up commit and the proposal status flips to
   `reverted`.

## What this phase deliberately does **not** do (deferred to Phase 73c)

* **GitHub-API integration / branch + PR flow.** The reserved env vars
  (`NEXA_SELF_IMPROVEMENT_GITHUB_TOKEN`, `NEXA_SELF_IMPROVEMENT_BASE_BRANCH`)
  are parsed so the schema stays stable, but no code reads them in 73b.
* **Auto-push to origin.** All commits are local. The operator runs
  `git push` manually.
* **Graceful in-process restart.** The running uvicorn process keeps the
  pre-apply code in memory until the operator restarts it.
* **Telegram approval.** The Mission Control web UI is the only approval
  surface in v1. A `/improvements` Telegram command is straightforward to
  add (mirrors the existing approvals/marketplace TG commands) but is
  out of scope here.
* **Auto-discovery of proposal seeds.** v1 takes the problem statement
  as **operator input**; the Phase 73 self-healing diagnose endpoint can
  be one-click promoted into a proposal seed in a future iteration, but
  there is no background loop that opens proposals on its own.
* **Embedding-based context selection.** The LLM only sees the files the
  operator explicitly listed (plus optional extras). No retrieval, no
  ranking — keeps the trust boundary obvious.

## Files touched

```
app/core/config.py                                         # 5+2 settings
.env.example                                                # synced
.env                                                        # synced
app/services/self_improvement/__init__.py                   # new
app/services/self_improvement/context.py                    # new
app/services/self_improvement/proposal.py                   # new
app/services/self_improvement/sandbox.py                    # new
app/api/routes/self_improvement.py                          # new
app/main.py                                                 # router include
web/lib/api/self_improvement.ts                             # new
web/lib/navigation.ts                                       # +Improvements
web/app/mission-control/(shell)/self-improvement/page.tsx   # new
tests/test_self_improvement_phase73b.py                     # new (27 cases)
docs/PHASE73B_SELF_IMPROVEMENT.md                           # this doc
```

## Notes for future maintainers

* The URL slug for the page is `/mission-control/self-improvement` (not
  `/mission-control/improvements`) on purpose — the Phase 48 identity
  lock (`tests/test_identity_final_phase48.py`) blocks the substring
  `/improve` anywhere under `web/`. Keep the slug as-is when adding new
  routes/links.
* The `self_improvement_proposals` table lives in `data/agent_audit.db`
  alongside the Phase 73 `mistakes` table. If you ever need to migrate
  it, do an in-place `ALTER TABLE` rather than a separate database file —
  the lazy `_init_db` pattern in `ProposalStore.__init__` is idempotent.
* `APPLY_REQUIRES_FRESH_SANDBOX_S` (currently 60s) lives at the top of
  `app/api/routes/self_improvement.py`. Tighten it to 30s once you've
  validated the loop in production; loosen with care.
* The sandbox runs `pytest` with the **same environment** as the
  surrounding API process. That's intentional — it lets sandbox runs see
  the same provider keys + DB connections + feature flags the running
  app sees, so a passing sandbox actually reflects production behavior.
  Side-effect-heavy tests should be excluded from the inferred targets
  by name (the inference rule is `tests/test_<stem>*.py` so a touched
  module without matching tests just runs the existing
  `tests/test_health.py` smoke fallback).

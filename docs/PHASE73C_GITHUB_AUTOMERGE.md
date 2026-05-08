# Phase 73c — Self-Improvement: GitHub Auto-Merge

> **TL;DR.** Phase 73c extends the Phase 73b self-improvement pipeline so an
> approved + sandbox-passed proposal can be turned into a real GitHub branch +
> PR, then merged via the REST API — all from Mission Control. Local apply
> (73b) and remote merge (73c) are deliberately separate terminal states; the
> operator picks which deployment path to use per proposal. Graceful in-process
> restart after merge is **deferred to Phase 73d** (we don't yet have a
> process supervisor on this box).

---

## 1. Spec audit and what we landed differently

Original spec (`Phase 73c: Self-Improvement – GitHub Auto-Merge & Graceful Restart`)
called for a synchronous PyGithub client, file-by-file commits via the GitHub
Contents API, and a `sys.exit(0)` restart endpoint. Three of those choices
would have caused real problems for us, so we adapted them.

| Spec | What we did instead | Why |
|---|---|---|
| `PyGithub` client (sync) wrapped in `async def` | Async `httpx.AsyncClient` (already a project dep) | `async def` over PyGithub still blocks the event loop — `asyncio.to_thread` was missing in the spec. Avoiding PyGithub also keeps deps lighter. |
| Per-file `commit_file` via Contents API (full-file replacement) | Re-use 73b's `git worktree`, `git apply` the diff, `git push origin <branch>`, then open the PR via REST | Unified diffs with surgical hunks across multiple files don't survive a "replace whole file" round-trip via the Contents API. Local apply matches what `git apply` produces. |
| `sys.exit(0)` restart endpoint | **Deferred to Phase 73d** | We have no process supervisor (no systemd / docker / pm2). `sys.exit` from a request handler kills the API and never comes back. `NEXA_SELF_IMPROVEMENT_AUTO_RESTART` is parsed but unused so 73d can wire it without a config migration. |
| `dependencies=[Depends(is_owner_role)]` | `_require_owner(db, app_user_id)` inside the body | Matches the existing 73/73.5/73b pattern. `is_owner_role` is a regular `bool` helper, not a FastAPI dependency. |
| Status `applied` reused for "merged" | New status `merged` (separate from `applied`) | 73b's local-apply flow stays a valid deployment path. The operator picks per proposal. |
| `/restart` endpoint | Not shipped in 73c | See above. |

CI caveat: the only GitHub Actions workflow on this repo right now is
`.github/workflows/mobile.yml`, scoped to `aethos-mobile/**`. PRs touching
`app/`, `tests/`, or `web/` will return `mergeable=true` immediately with
**zero status checks**. The local sandbox (73b) is therefore the actual
safety net, not the GitHub-side `mergeable` flag. The merge endpoint
preserves the 73b 60-second-fresh-sandbox gate so a stale approval can't be
used to push something untested.

---

## 2. Configuration

`.env.example` and `.env` (synced; defaults are off) — see also
`app/core/config.py` for the `Settings` fields.

```bash
# Master switch (default off; opt-in)
NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=false
# Fine-grained PAT scoped to *this* repo with Contents:write + PRs:write.
NEXA_SELF_IMPROVEMENT_GITHUB_TOKEN=
NEXA_SELF_IMPROVEMENT_GITHUB_OWNER=pilotmain
NEXA_SELF_IMPROVEMENT_GITHUB_REPO=aethos
NEXA_SELF_IMPROVEMENT_GITHUB_BASE_BRANCH=main
NEXA_SELF_IMPROVEMENT_GITHUB_PR_TITLE_PREFIX=[self-improvement]
NEXA_SELF_IMPROVEMENT_GITHUB_BRANCH_PREFIX=self-improvement/
NEXA_SELF_IMPROVEMENT_GITHUB_MERGE_METHOD=squash   # squash | merge | rebase
# Reserved for Phase 73d (parsed but unused in 73c)
NEXA_SELF_IMPROVEMENT_AUTO_RESTART=false
```

Token handling: the PAT is read from `Settings` at request time, attached as
an `Authorization: Bearer <token>` header, and used to construct an
in-memory tokenized push URL of the form
`https://x-access-token:<token>@github.com/<owner>/<repo>.git`.
It is **never** logged or echoed — the github client deliberately strips
the token out of any error message that propagates to the API surface
(`_redact_token`).

---

## 3. New backend pieces

### `app/services/self_improvement/github_client.py` (new)

Async `GitHubClient` over `httpx.AsyncClient`:

- `push_diff_branch(proposal_id, diff_text, commit_message, ...)` — creates
  an isolated `git worktree` rooted at the configured base branch, applies
  the diff, commits, pushes to `origin` under
  `<branch_prefix>/<proposal_id>-<rand>`. Always cleans up the worktree.
- `open_pull_request(head_branch, title, body, base_branch=None)` — POST
  `/repos/{o}/{r}/pulls`.
- `get_pull_request_status(pr_number)` — GET; returns `mergeable`,
  `mergeable_state`, `merged`, head/base refs.
- `merge_pull_request(pr_number, ...)` — PUT
  `/repos/{o}/{r}/pulls/{n}/merge` with the configured merge method.
  Maps GitHub's `405` (not mergeable) and `409` (merge conflict) to
  structured `GitHubError(code=...)`.
- `open_revert_pr(merge_commit_sha, title, body)` — fresh worktree,
  `git revert --no-edit -m 1 <sha>` (falls back to plain revert for
  squash-merge non-merge commits), push, open PR.

### `app/services/self_improvement/proposal.py` (extended)

New statuses: `pr_open`, `merged`, `revert_pr_open` — see `VALID_STATUSES`.
New columns added via lazy idempotent `ALTER TABLE` on store init (so a
73b DB upgrades to 73c on next boot without a manual migration):

- `pr_number`, `pr_url`, `github_branch`, `merge_commit_sha`
- `revert_pr_number`, `revert_pr_url`

New writer: `set_github_state(...)` — `COALESCE`-based partial update so
callers can patch one field without clobbering others.

### `app/api/routes/self_improvement.py` (extended)

| Endpoint | Method | Status preconditions | Auth |
|---|---|---|---|
| `/api/v1/self_improvement/-/capabilities` | GET | always | any web user |
| `/api/v1/self_improvement/{id}/open-pr` | POST | `approved` + sandbox passed within 60s + GitHub enabled | owner |
| `/api/v1/self_improvement/{id}/pr-status` | GET | proposal has `pr_number` + GitHub enabled | owner |
| `/api/v1/self_improvement/{id}/merge-pr` | POST | `pr_open` + sandbox fresh (60s) + GitHub `mergeable=True` | owner |
| `/api/v1/self_improvement/{id}/revert-merge` | POST | `merged` + has `merge_commit_sha` | owner |

GitHub-flow endpoints return `404` when
`NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=false`. `/{id}/revert-merge` requires
GitHub enabled too because it opens a fresh remote PR; the 73b local-only
`/{id}/revert` stays in place for the local-apply flow.

`GitHubError` codes are mapped:
- `github_disabled`, `github_token_missing` → `503`
- `pr_not_found`, `github_repo_not_configured` → `404`
- `not_mergeable`, `merge_conflict` → `409`
- `diff_does_not_apply`, `diff_apply_failed` → `412`
- `github_network_error` → `502`
- everything else → `500`

The capabilities path uses `/-/capabilities` (a two-segment subpath under
the router prefix) instead of `/_capabilities` to avoid collision with the
`/{proposal_id}` route — single-segment routes registered earlier would
swallow `_capabilities` as a proposal id.

---

## 4. Web UI additions

`web/app/mission-control/(shell)/self-improvement/page.tsx`:

- Loads `selfImprovementCapabilities()` once on mount and renders an
  inline banner showing whether the GitHub flow is enabled / configured.
- Per-row buttons (gated by `caps.github.enabled` so they vanish entirely
  when the flow is off):
  - **Open PR** — visible while `status==approved`. Calls `/open-pr`,
    flashes the new PR number + head branch.
  - **Refresh PR status** — visible while `status==pr_open`. Calls
    `/pr-status` and reports `mergeable`, `merged`, `mergeable_state`.
  - **Merge if mergeable** — visible while `status==pr_open`. Calls
    `/merge-pr`; primary-styled button so it visually contrasts with
    the read-only refresh.
  - **Revert via PR** — visible while `status==merged`. Calls
    `/revert-merge`.
- New per-row line items render when the proposal has `pr_number`,
  `merge_commit_sha`, or `revert_pr_number` so the operator can see /
  click straight through to the GitHub PR URLs.

`web/lib/api/self_improvement.ts`:

- Extended `SelfImprovementProposal` with the six new GitHub fields.
- Extended `SelfImprovementStatus` with `pr_open`, `merged`,
  `revert_pr_open`.
- Five new client functions and matching response types
  (`SelfImprovementCapabilities`, `OpenPrResponse`, `PrStatusResponse`,
  `MergePrResponse`, `RevertMergeResponse`).

---

## 5. End-to-end operator flow (GitHub mode)

1. Operator opens Mission Control → Improvements, fills the **Propose** form.
2. LLM generates a unified diff; row appears with status `pending`.
3. Operator clicks **Sandbox** — `git worktree` apply + `compileall` +
   targeted `pytest`. Status → `pending` with `sandbox_result.success=true`.
4. Operator clicks **Approve**. Status → `approved`.
5. Operator clicks **Open PR** (only visible if
   `NEXA_SELF_IMPROVEMENT_GITHUB_ENABLED=true`). Backend pushes the diff to
   `self-improvement/<id>-<rand>` on `origin`, opens a PR. Status →
   `pr_open`. Row shows the linked PR number.
6. *(Optional)* Operator clicks **Refresh PR status** — surfaces GitHub's
   `mergeable` / `mergeable_state` / `merged`. With no remote CI on this
   repo, this just confirms there's no conflict.
7. Operator clicks **Merge if mergeable**. Backend re-checks
   `mergeable=True` and the 60-second sandbox freshness gate, then PUT
   `/pulls/{n}/merge` with the configured merge method. Status →
   `merged`. Row shows `merge_commit_sha`.
8. Operator runs `git pull` locally and restarts the API to pick up the
   new code. (Auto-restart deferred to 73d.)
9. Rollback: click **Revert via PR**. Backend opens a fresh PR that
   `git revert`s the merge commit and pushes to a new branch. Status →
   `revert_pr_open`. Operator merges that PR on GitHub the normal way,
   then `git pull` + restart.

---

## 6. Tests

`tests/test_self_improvement_github_phase73c.py` — 24 tests, all green.

- **github_client**: settings plumbing, merge-method fallback, token
  redaction, error-message extraction, happy-path `open_pull_request`
  via `httpx.MockTransport`, error mapping for `422` and `405`/`409`.
- **proposal store**: lazy migration adds the 73c columns to a
  pre-existing 73b DB, `set_github_state` partial update, all new statuses
  round-trip.
- **router**: `/-/capabilities` shape with GitHub on / off, `/open-pr`
  happy path with mocked client, `404` when GitHub disabled, `403` for
  non-owner, `409` when not approved, `412` without sandbox; `/pr-status`
  `409` with no PR; `/merge-pr` happy path, `409` when `mergeable=False`,
  `409` when GitHub still computing; `/revert-merge` happy path, `409`
  when not in `merged` state.

No real network or `git` subprocess calls are made — `push_diff_branch`
and `open_revert_pr` are mocked at the router boundary via a
`_FakeGitHubClient` stub.

---

## 7. Deferred / out-of-scope

- **Graceful in-process restart** (`NEXA_SELF_IMPROVEMENT_AUTO_RESTART=true`,
  `app/core/restart.py`, `/restart` endpoint) — Phase 73d. Requires a
  process supervisor (systemd unit / docker compose / pm2) so an exit
  actually triggers a restart.
- **Branch-protection-aware merge** (wait for required status checks before
  merging) — currently we only check `mergeable`. Once a real Python/web
  CI workflow is added, the merge endpoint can be tightened to gate on
  `combined_status` / `check_runs`.
- **Background mergeability poller** — operator polls on demand via
  the **Refresh PR status** button. A scheduled poller would be a
  Phase 73d nicety.
- **Revert PR auto-merge** — the revert PR is opened but the operator
  must merge it themselves on GitHub. Auto-merging the revert is symmetric
  with the original auto-merge gate and could be added later.

---

## 8. Files changed in 73c

| File | Action |
|---|---|
| `app/core/config.py` | Add `nexa_self_improvement_github_enabled`, `_owner`, `_repo`, `_base_branch` (rename), `_pr_title_prefix`, `_branch_prefix`, `_merge_method`; reserve `_auto_restart` for 73d |
| `.env.example` / `.env` | Sync the new vars with comments |
| `app/services/self_improvement/github_client.py` | **new** — async httpx GitHub client + `push_diff_branch` worktree helper |
| `app/services/self_improvement/proposal.py` | Extend with `STATUS_PR_OPEN` / `STATUS_MERGED` / `STATUS_REVERT_PR_OPEN`, new dataclass fields, lazy-migration `ALTER TABLE` for the new columns, `set_github_state(...)` writer |
| `app/api/routes/self_improvement.py` | Extend with `/-/capabilities`, `/{id}/open-pr`, `/{id}/pr-status`, `/{id}/merge-pr`, `/{id}/revert-merge` |
| `web/lib/api/self_improvement.ts` | Extend status union + dataclass + add 5 client functions and 5 response types |
| `web/app/mission-control/(shell)/self-improvement/page.tsx` | Capabilities banner + 4 new per-row buttons + new line-items for PR / merge / revert state |
| `tests/test_self_improvement_github_phase73c.py` | **new** — 24 tests, no real network |
| `docs/PHASE73C_GITHUB_AUTOMERGE.md` | **new** — this document |

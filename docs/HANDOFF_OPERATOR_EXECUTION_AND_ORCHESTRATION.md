# Handoff: Operator mode, execution loop, and orchestration work

**Audience:** Next engineer or future you picking this up cold.  
**Scope:** Everything implemented in-repo for “Nexa acts like an operator / execution gateway” workstreams **without** reproducing any secret values or API keys. **Do not** paste `.env` contents into tickets or this doc—reference variable **names** only.

---

## 1. Why this work exists

Problems addressed (product intent):

- Users asking for infra/repo work were getting **generic chat** (“I can guide you”, “paste logs”) instead of **bounded CLI attempts** and **exact blockers**.
- **Retry / resume / probe** paths were duplicated or easy to miss in routing.
- **Operator mode** should reduce confirmation loops and favor **act → progress → proof** over narration.
- **Phase “next”** adds **gated** write/deploy/test/verify steps behind explicit env flags and host executor.

---

## 2. High-level architecture (after changes)

**Gateway admission (`app/services/gateway/runtime.py`)** — order matters:

1. **Credential / secret chat** — `maybe_handle_external_credential_chat_turn` (unchanged responsibility).
2. **`try_operator_execution`** — `app/services/operator_execution_loop.py` (only when `NEXA_OPERATOR_MODE` is on; Vercel/GitHub/workspace phases + gated actions).
3. **`try_execute_or_explain`** — `app/services/execution_loop.py` (Railway-style bounded runner, retry/resume/probe, access gates).
4. Structured route (missions, dev, etc.), approvals, then full chat / LLM.

**Telegram** (`try_structured_turn`) mirrors the same **cred → operator loop → execution loop** before structured routing. **`continue_after_structured`** resets `operator_execution_attempted` so `handle_full_chat` can still run operator/execution paths when appropriate.

**Payload keys** (when handled):

- Execution loop: `execution_loop`, `ran`, `blocker`, `verified`, `intent: execution_loop`.
- Operator loop: `operator_execution`, `operator_provider`, `operator_evidence`, `ran`, `verified`, `blocker`, `intent: operator_execution`.

---

## 3. Major modules added

| Path | Role |
|------|------|
| `app/services/execution_loop.py` | Central **bounded external execution** router: retry phrases, resume fragment, direct probe, Railway access gate, `run_bounded_railway_repo_investigation`. Returns `ExecutionLoopResult`. |
| `app/services/operator_execution_loop.py` | **Operator orchestration** entry: `OperatorExecutionResult`, `try_operator_execution`. Vercel/GitHub/local diagnostics; phase-only workspace flows; optional embedded diff; merges phased actions. |
| `app/services/operator_runners/` | **Read-only** provider helpers: `base.py`, `vercel.py`, `railway.py` (delegates to existing bounded runner), `github.py`, `local_dev.py` (`git status` at path or registered workspace). |
| `app/services/operator_execution_actions.py` | **Gated** mutating actions: `apply_code_fix` (patch), `run_tests`, `commit_and_push`, `deploy_vercel`, `deploy_railway`, `verify_http_head`, `retry_with_backoff`, gates. |

---

## 4. Important existing files changed

| File | What changed |
|------|----------------|
| `app/services/gateway/runtime.py` | Wired `try_execute_or_explain` and `try_operator_execution`; removed duplicate retry/resume/probe from `handle_full_chat`; operator mode skips medium dev confirmation; `gateway_finalize_chat_reply` scrubs repeated “confirm again” spam when operator mode is on; extras `execution_loop_attempted` / `operator_execution_attempted`. |
| `app/services/external_execution_session.py` | **CLI locally** / **use CLI** parsing; probe phrases imply `local_cli`; fragment **never drops** `auth_method`/`deploy_mode`; operator-mode defaults for deploy prefs; `_cli_locally_grants_probe` + relaxed direct probe; `scrub_operator_idle_loop_phrases`. |
| `app/core/config.py` | New flags: `nexa_operator_mode`, `nexa_operator_allow_write`, `nexa_operator_allow_deploy`, `nexa_operator_auto_retry`, `nexa_execution_confirm_medium` (documented in example env). |
| `.cursor/rules/env-vars-sync-dotenv.mdc` | **Mandatory**: new Settings/env vars must appear in **both** `.env.example` and local `.env` in the same task (no secrets in repo). |
| `.cursor/rules/env-vars-sync-with-settings.mdc` | Cross-references dotenv rule. |
| `.env.example` | Documented operator, execution, host executor, Railway/GitHub token **names** (placeholders only). |

**Not changed in this handoff’s scope:** Mission Control UI for live operator state, credential vault productization, interactive `vercel login` automation, full retry policy across distributed workers.

---

## 5. Configuration reference (names only — no values)

These are loaded via **Pydantic `Settings`** (typically `NEXA_*` in the environment). **Never** commit real tokens; `.env` is gitignored.

| Variable | Purpose (safe defaults in code / example) |
|----------|---------------------------------------------|
| `NEXA_OPERATOR_MODE` | Enables operator execution loop + related behavior (default **off**). |
| `NEXA_OPERATOR_ALLOW_WRITE` | Allows git add/commit/push and patch apply paths (default **off**). |
| `NEXA_OPERATOR_ALLOW_DEPLOY` | Allows `vercel deploy` / `railway up` from operator actions (default **off**). |
| `NEXA_OPERATOR_AUTO_RETRY` | Retries patch dry-run/apply with backoff in actions layer (default **off**). |
| `NEXA_EXECUTION_CONFIRM_MEDIUM` | When on, medium-confidence dev auto-run may ask for confirmation unless operator mode bypasses (see gateway). |
| `NEXA_HOST_EXECUTOR_ENABLED` | Required (with operator flags) for mutating operator actions on the worker. |
| `NEXA_EXTERNAL_EXECUTION_RUNNER_ENABLED` | Bounded Railway subprocess runner for external execution path. |
| `HOST_EXECUTOR_WORK_ROOT`, `HOST_EXECUTOR_TIMEOUT_SECONDS`, `HOST_EXECUTOR_MAX_FILE_BYTES` | Host executor workspace/time/size limits. |
| `RAILWAY_TOKEN`, `RAILWAY_API_TOKEN`, `GITHUB_TOKEN` | **Secrets** — must be set by the operator on the worker; **do not** document values here. |

Local `.env` should mirror **names** from `.env.example`; values are the operator’s responsibility.

---

## 6. Tests added (searchable)

Under `tests/`:

- **Execution loop:** `test_execution_loop_*.py` (router, Railway attempts, blockers, retry, secret setup copy, no generic guidance, no fake mission, progress).
- **Operator mode (session/gateway):** `test_operator_mode.py`, `test_external_execution_followup.py` (updated expectations where intent is `execution_loop`).
- **Operator orchestration:** `test_operator_execution_loop.py`, `test_operator_vercel_runner.py`, `test_operator_railway_runner.py`, `test_operator_github_runner.py`, `test_operator_no_fake_success.py`, `test_operator_no_repeated_confirmation.py`, `test_operator_truth_verification.py`.
- **Phase next actions:** `test_operator_execution_actions.py`, `test_operator_full_execution_flow.py`, `test_operator_deploy_vercel.py`, `test_operator_commit_push.py`.

Run:

```bash
.venv/bin/pytest tests/test_execution_loop_*.py tests/test_operator_*.py tests/test_external_execution_followup.py tests/test_external_execution_retry_no_loop.py -q
```

---

## 7. What actually works today

- **Execution loop** runs **before** generic LLM / mission parsing for web `_route` and Telegram `try_structured_turn`, after credential handling.
- **Retry / resume / probe** for external execution are centralized in **`try_execute_or_explain`** (not duplicated in `handle_full_chat`).
- **Operator mode** reduces nag copy, skips **medium** dev confirmation when enabled, and strengthens **CLI locally** / follow-up parsing.
- **Operator execution loop** (when `NEXA_OPERATOR_MODE=true`): read-only Vercel/GitHub/git diagnostics; **phase-only** turns with a **single** registered workspace; optional **` ```diff ` … `` `** patch path; **gated** test/commit/push/deploy/verify when flags + host executor allow.
- **Truth helper** softens unverified “deployed successfully” style language when not verified.

---

## 8. Known gaps / “not magical yet”

- **Deploy/write** requires explicit flags and **host executor**; still no end-to-end “one sentence fixes production everywhere” without a real workspace and credentials on the worker.
- **Token in chat** still flows through existing **credential** handlers—not a new vault product in this work.
- **Mission Control** does not yet show operator phases, last command, or evidence stream as in the long-term spec.
- **Interactive logins** (`vercel login`, etc.) are not orchestrated as automated flows.

---

## 9. Git history (how to see exact diffs)

All of this is on **`main`** on the canonical remote. Use messages and file paths:

```bash
git log --oneline -20 -- app/services/execution_loop.py app/services/operator_execution_loop.py \
  app/services/operator_runners/ app/services/operator_execution_actions.py \
  app/services/gateway/runtime.py app/services/external_execution_session.py app/core/config.py
```

Representative commit **themes** (subjects may vary slightly):

- Central execution loop + gateway wiring + execution loop tests.
- Operator mode + external session confirmation fixes + env sync rules.
- Operator execution loop + `operator_runners` package + gateway operator branch.
- Phase next: `operator_execution_actions` + phased loop + new Settings + tests.

---

## 10. Operational reminder

After changing any of the **`NEXA_*`** flags, **restart the API and Telegram bot** so processes reload `Settings`. Do not commit `.env` or paste secrets into docs or PRs.

---

*End of handoff document.*

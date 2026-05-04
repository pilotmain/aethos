# Week 1 (scoped): local-git phrasing vs Railway default

## What this change does

User messages that clearly mean **“work on git on my machine / in local”** (e.g. *check this git in local*) now:

- Set **`ignore_railway`** in `extract_focused_intent` (with or without “push to remote”).
- Return **`True`** from `should_skip_railway_bounded_path` when there is **no** Railway URL and the user did not name **Railway** in text — so the bounded **Railway** investigation in `try_execute_or_explain` is **not** the default.
- **Do not** classify the turn as `looks_like_external_execution` when the only “hosted” signal is local-git wording (see `intent_classifier`).

## What this does **not** do

- **No** scanning of `/Users/...` or arbitrary host directories from chat (security + Docker workers do not have your Mac paths unless bind-mounted).
- **No** `NEXA_OPERATOR_AUTO_PROCEED`, no auto queue of `file_write` / `git_commit` / `git_push`.
- **No** “fix 404 on GitHub” for repos that only exist on disk — remote **404** is a **GitHub** fact; the worker’s **`HOST_EXECUTOR_WORK_ROOT`** is the supported mutation boundary.

## Files touched

- `app/services/intent_focus_filter.py` — `local_git_workspace` + `ignore_railway`
- `app/services/provider_router.py` — early skip for local-git phrasing
- `app/services/execution_loop.py` — `_strong_hosted_or_deploy_cue` respects local-git focus
- `app/services/intent_classifier.py` — local-git guard for `looks_like_external_execution`
- `tests/test_week1_local_git_routing.py`, `tests/test_focused_response.py`

## Review after deploy

If users still see Railway copy, capture the **exact** user line and logs: another route (mission, operator, LLM) may be answering, not `try_execute_or_explain`.

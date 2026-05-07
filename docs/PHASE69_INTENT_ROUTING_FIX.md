# Phase 69 — Fix Intent Routing: Prevent Dev Agent Hijacking

## Problem

General questions like *"what do you need to deploy to AWS?"* were being pulled into
the dev pipeline (`stuck_dev` → `_maybe_auto_dev_investigation`,
`should_prompt_for_dev_workspace_help`) because the LLM intent classifier — and the
deterministic `looks_like_stuck_dev` heuristic — both treat any message containing
`deploy` / `aws` / `kubernetes` plus an interrogative starter (`why `, `how `) as a
dev-blockage cue.

The result: an informational query was answered with workspace-setup prompts or an
attempt to run a dev investigation instead of plain chat.

## Fix

Add a deterministic question-shape pre-classifier in `app/services/intent_classifier.py`
that runs **before** the LLM call and short-circuits to the curated fallback when the
message is clearly informational.

### `looks_like_informational_question(text, conversation_snapshot=None)`

Returns `True` only when **all** of the following hold:

1. The message is interrogative — ends with `?` **or** starts with one of:
   `what`, `how`, `why`, `where`, `when`, `who`, `can you`, `could you`, `would you`,
   `should i/we`, `do you`, `does it/the`, `is it/there`, `are you`, `am i`,
   `tell me`, `explain`, `i'm curious`.
2. No URL is present.
3. No hosted provider name is present (`railway`, `render.com`, `fly.io`, `heroku`,
   `vercel`, `netlify`, `cloudflare`).
4. No imperative cue is present (`now`, `go ahead`, `let's deploy`, `let me push`,
   `do it`, `ship it`, `kick off`, `run it`, `please run/deploy/push/commit`,
   `right now`).
5. The message does **not** start with a bare action verb (`deploy`, `push`,
   `commit`, `run`, `execute`, `build`, `start`, `stop`, `migrate`, `rollback`,
   `merge`, `ship`, `kick`).
6. None of the existing deterministic intents fire — `looks_like_orchestrate_system`,
   `looks_like_external_execution`, `looks_like_external_execution_continue`,
   `looks_like_external_investigation`, `looks_like_analysis`.
7. `looks_like_stuck_dev` returns `False`, **or** the only pain match is the bare
   `why ` starter (Kubernetes / docker curiosity questions land here without a real
   pain phrase like `broken`, `failing`, `error`, `stuck`, `can't`, `figure out`,
   `debug`, `how do i fix`).

### `get_intent` short-circuit

When `Settings.nexa_informational_question_skip_llm` is `True` (default) and
`looks_like_informational_question(text)` matches, `get_intent` calls
`classify_intent_fallback(...)` and coerces any leftover action-leaning intents
(`stuck_dev`, `stuck`, `analysis`, `external_execution`, `external_execution_continue`,
`external_investigation`, `orchestrate_system`, `brain_dump`) to `general_chat`. The
fallback's curated capability / correction / followup paths still win on their own
phrases (e.g. *"can you do design?"* → `capability_question`).

## Settings

| Env var | Default | Purpose |
|---|---|---|
| `NEXA_INFORMATIONAL_QUESTION_SKIP_LLM` | `true` | Toggle the Phase 69 short-circuit. Set `false` to restore the prior LLM-only routing. |

Synced in `.env.example` and the repo-root `.env` per workspace rules.

## Behavior change matrix

| Message | Before | After |
|---|---|---|
| `what do you need to deploy to AWS?` | dev pipeline (workspace prompt) | `general_chat` |
| `how would I deploy an app?` | dev pipeline | `general_chat` |
| `Can you explain AWS deployment?` | dev pipeline | `general_chat` |
| `Tell me about deploying to the cloud` | LLM-classified | `general_chat` |
| `Why does Kubernetes ingress exist?` | `stuck_dev` (false positive) | `general_chat` |
| `Can you do design work for me?` | LLM-classified | `capability_question` |
| `what can you do?` | `capability_question` | `capability_question` (unchanged) |
| `Why is my Railway service unhealthy` | `external_investigation` | `external_investigation` (unchanged) |
| `Can you check Railway, fix repo, push, redeploy, and report?` | `external_execution` | `external_execution` (unchanged) |
| `kubernetes ingress returns 502 every time — ERROR` | `stuck_dev` | `stuck_dev` (unchanged — pain word `error`) |
| `deploy now`, `push to production`, `ship it` | dev / external_execution | dev / external_execution (unchanged) |

## Files touched

| File | Change |
|---|---|
| `app/core/config.py` | New `nexa_informational_question_skip_llm` setting (default `True`) |
| `app/services/intent_classifier.py` | New `looks_like_informational_question` helper + `get_intent` short-circuit |
| `.env.example` | New `NEXA_INFORMATIONAL_QUESTION_SKIP_LLM=true` entry |
| `.env` | Same entry mirrored for the local operator |
| `tests/test_intent_question_routing_phase69.py` | New deterministic test coverage (10 cases) |
| `docs/PHASE69_INTENT_ROUTING_FIX.md` | This document |

## Verification

```bash
.venv/bin/python -m compileall -q app
.venv/bin/python -m pytest tests/test_intent_question_routing_phase69.py \
    tests/test_intent_action_flow.py \
    tests/test_intent_orchestration_routing.py -q
# 37 passed

.venv/bin/python -m pytest tests/ -q -k \
    "intent or external_execution or capability or gateway or stuck_dev or operator_execution or behavior"
# 320 passed
```

The Phase 69 short-circuit only suppresses LLM round-trips for messages that already
look like questions and clear every existing deterministic gate, so the dev /
external-execution / orchestrate paths remain authoritative for their own cues.

# Week 2 v1: Host action chains

## Overview

`host_action: chain` runs multiple **allowlisted** inner host actions **in sequence** inside **one** host-executor job (one approval), when enabled on the worker.

Nested chains and NL→chain auto-mapping are **out of scope** for v1 (see below).

## Enabling chains

In `.env` on the **worker** (and anywhere that evaluates permissions if enforcement is on):

```bash
NEXA_HOST_EXECUTOR_CHAIN_ENABLED=true
```

Optional:

```bash
NEXA_HOST_EXECUTOR_CHAIN_MAX_STEPS=10
# Comma-separated override; leave empty for the default inner set
NEXA_HOST_EXECUTOR_CHAIN_ALLOWED_ACTIONS=file_write,git_commit,git_push,vercel_projects_list
```

## Payload shape

Top-level fields (same job as other host actions — no extra wrapper):

```json
{
  "host_action": "chain",
  "actions": [
    {
      "host_action": "file_write",
      "relative_path": "README.md",
      "content": "# Service stopped"
    },
    {
      "host_action": "git_commit",
      "commit_message": "docs: update README",
      "cwd_relative": "my-repo"
    },
    {
      "host_action": "git_push",
      "cwd_relative": "my-repo"
    }
  ],
  "stop_on_failure": true,
  "cwd_relative": "my-repo"
}
```

- `stop_on_failure` defaults to `true`. When set, the chain **stops** after the first step whose **text output** indicates failure (e.g. non-zero exit messages from git/vercel).
- You may set `cwd_relative` on the **chain** object; it is merged into inner steps that use a working directory (git, allowlisted `run_command`, Vercel list) when the step omits its own `cwd_relative`.

## Allowed inner actions (default)

Unless overridden by `NEXA_HOST_EXECUTOR_CHAIN_ALLOWED_ACTIONS`:

| `host_action`         | Notes |
|----------------------|--------|
| `file_write`         | Same rules as a single `file_write` step |
| `git_commit`         | Stages all, fixed message |
| `git_push`           | Optional `push_remote` / `push_ref` per step |
| `vercel_projects_list` | Read-only CLI |

`vercel_remove` and other actions are **not** in the default inner set.

## Security

- Chains are **off by default** (`NEXA_HOST_EXECUTOR_CHAIN_ENABLED=false`).
- When access permissions are enforced, **each** inner step is checked against grants before any step runs.
- Provenance rules still apply; `chain` is treated as a privileged action (same family as other mutating host tools).

## Rollback

```bash
NEXA_HOST_EXECUTOR_CHAIN_ENABLED=false
```

## Not in Week 2 v1

- Natural-language mapping to chain payloads in the gateway (planned follow-up).
- Async chains or nested `chain` inside `chain`.
- Automatic retry or rollback after failure.

## Related docs

- `docs/RUNBOOK_HOST_EXECUTOR_GIT_README.md` — README / commit / push patterns
- `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` — operator vs host executor

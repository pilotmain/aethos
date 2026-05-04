# Week 2: Host action chains (v1 + v2)

## Overview

`host_action: chain` runs multiple **allowlisted** inner host actions **in sequence** inside **one** host-executor job (one approval), when enabled on the worker.

Nested chains are not supported. **Week 2 v2** adds optional, narrow **NL → chain** mapping (see below).

## macOS + Docker: repos under `/Users/raya`

If your git repos live on the Mac under **`/Users/raya`**, the API container cannot see them until you **bind-mount** that directory and point **`HOST_EXECUTOR_WORK_ROOT`** at the **same path inside the container**.

Example `docker-compose.override.yml`:

```yaml
services:
  api:
    volumes:
      - /Users/raya:/Users/raya
```

Example `.env` (inside-container path matches the mount target):

```bash
HOST_EXECUTOR_WORK_ROOT=/Users/raya
```

Then payload paths such as `pilot-command-center/README.md` are relative to `/Users/raya` (i.e. `/Users/raya/pilot-command-center/README.md` inside the container). Use a **narrower** mount (single repo) if you do not want the whole home tree visible in the container.

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

## Week 2 v2: NL → README / commit / push chain (optional)

When **`NEXA_NL_TO_CHAIN_ENABLED=true`** and **`NEXA_HOST_EXECUTOR_CHAIN_ENABLED=true`**, a short user line that both **asks to add/create/write a README** and **mentions push** can be turned into the same **file_write + git_commit + git_push** chain as JSON (still **confirm → queue → approve**; no new HTTP API).

Phrases (examples):

- `add a README and push`
- `create readme saying "Service stopped" and push`

Optional quoted titles:

- `saying '…'` / `saying "…"`
- `with content '…'`
- `title '…'` / `titled "…"`

If no title is parsed, the README body uses a small default title line.

**Disabled by default** — set on any process that runs host inference (API):

```bash
NEXA_NL_TO_CHAIN_ENABLED=true
```

Active workspace project base (when set) still **prefixes paths** and **sets `cwd_relative`** for git steps via `merge_payload_with_project_base` (same as other host tools).

## Not in scope

- Async chains or nested `chain` inside `chain`.
- Automatic retry or rollback after failure.
- Broad NL (multi-sentence planning, arbitrary commands); v2 is intentionally narrow.

## Related docs

- `docs/RUNBOOK_HOST_EXECUTOR_GIT_README.md` — README / commit / push patterns
- `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` — operator vs host executor

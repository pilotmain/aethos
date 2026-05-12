# Sandbox execution

## Overview

The sandbox can **draft an LLM-generated plan** of allowlisted actions (`read_file`, `write_file`, `run_command`, …), store it pending your **yes/no**, then run it under the configured workspace with **backup + rollback** on failure.

## Enabling sandbox

In `.env` (see `.env.example`):

```bash
NEXA_SANDBOX_EXECUTION_ENABLED=true
USE_REAL_LLM=true
```

Owner / auto-approve gates apply — see `app/services/gateway/sandbox_nl.py`.

## How it works

1. User describes a change (e.g. “Development change … in styles.css”).
2. Planner produces JSON actions (validated by `action_allowlist`).
3. User replies **yes** to execute (or **no** to cancel).
4. Executor runs steps under the workspace root.

## Security

- Workspace-only paths (no `..`, no absolute escape).
- Command token allowlist for `run_command`.
- **read_file** resolves paths under the workspace and latest todo-style app folder when needed.

## Related

- [File operations](file-operations.md)
- [Command execution](command-execution.md)

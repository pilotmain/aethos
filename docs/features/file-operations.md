# File operations

## Creating files

Examples:

- “Make a file test.txt that says Hello World”
- “Write notes.txt with meeting notes”

Host executor and sandbox paths enforce **workspace policy** — see [WORKSPACE_AND_PERMISSIONS.md](../WORKSPACE_AND_PERMISSIONS.md).

## Reading files

- **Gateway fast path:** `Development read|show|cat|display <path>` (owner + sandbox enabled) — see `app/services/gateway/sandbox_nl.py`.
- **Sandbox plan:** `read_file` actions resolve under `NEXA_WORKSPACE_ROOT`, including todo-style subfolders — see `app/services/sandbox/plan_executor.py`.

## Modifying files

Examples:

- “Development change background to blue in styles.css”
- “Development add a new function to app.js”

Larger edits may go through **sandbox plan → approval → execute** or **developer sub-agents** depending on routing.

## File location

Operations are confined to the configured workspace (typically **`NEXA_WORKSPACE_ROOT`** / `NEXA_SANDBOX_EXECUTION_WORKSPACE`).

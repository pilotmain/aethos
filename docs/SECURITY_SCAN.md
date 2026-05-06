# Security scanning (heuristic)

Orchestration agents in **qa** / **security** domains (and names like `qa_agent`, `security_agent`) run a **synchronous, static** scan of a workspace path through:

- `app/services/qa_agent/security_review.py` — `run_security_review_sync` (resolves path from the user message, then calls the scanner)
- `app/services/skills/builtin/security_scanner.py` — `scan_security` (file walk + pattern heuristics)

## What it is not

- Not a full SAST/SCA product: no guarantee of finding all vulnerabilities.
- Complement with `pip-audit`, `npm audit`, and your org’s real security process for production.

## Using it

- **Telegram:** `@<qa_agent> security scan /path/to/repo` (or a path segment the workspace resolver accepts).
- **API:** `POST /api/v1/agents/execute/<name>` with `{"task":"security scan /path"}` and `X-User-Id` (see [API.md](API.md)).

Path resolution honors workspace roots and permissions; see [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md).

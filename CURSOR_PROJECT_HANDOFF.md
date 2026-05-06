# Moved

Internal planning handoffs for maintainers and agents live under **`~/.aethos/docs/handoffs/`** (for example `CURSOR_HANDOFF.md`) — they are **not** tracked in this repository.

This stub stays at the repo root so older links, bookmarks, and file history still resolve. **Do not** duplicate long-form handoff here — that became a second source of truth and drifted from the product.

**Code work** from Telegram should flow through the **dev executor** (`dev_executor` jobs → `scripts/dev_agent_executor.py`, Codex when installed), not a parallel “only write a `.md` in `.agent_tasks/`” path. See the doc above for guardrails and job model.

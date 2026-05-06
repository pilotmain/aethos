"""
Optional UX: when a turn looks like “local git workspace” work, mention host action chains.

See ``~/.aethos/docs/handoffs/WEEK2_HOST_ACTION_CHAINS.md`` (local handoff pack).
"""

from __future__ import annotations

from typing import Any


def get_local_git_chain_clarification(repo_hint: str | None = None) -> str:
    """
    Return copy for using ``host_action: chain`` to batch file write + commit + push
    under a single job approval.
    """
    repo_part = f" on `{repo_hint}`" if (repo_hint or "").strip() else ""

    return f"""
📁 Local git context detected{repo_part}.

**To add a README, commit, and push in one approval (chain):**

```json
{{
  "host_action": "chain",
  "actions": [
    {{"host_action": "file_write", "relative_path": "README.md", "content": "Your content here"}},
    {{"host_action": "git_commit", "commit_message": "docs: update README"}},
    {{"host_action": "git_push"}}
  ],
  "stop_on_failure": true
}}
```

**Or run three separate host jobs** (file_write, then git_commit, then git_push) for three approvals.

Enable on the worker: `NEXA_HOST_EXECUTOR_CHAIN_ENABLED=1`

Details: `~/.aethos/docs/handoffs/WEEK2_HOST_ACTION_CHAINS.md` (local handoff pack)
""".strip()


def append_chain_clarification_if_needed(response: str, intent_flags: dict[str, Any]) -> str:
    """Append chain hint when ``local_git_workspace`` is set and the reply has not already covered chains."""
    if not intent_flags.get("local_git_workspace"):
        return response
    if "chain" in (response or "").lower():
        return response
    return (response or "").rstrip() + "\n\n" + get_local_git_chain_clarification()

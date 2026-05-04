"""
User-facing copy appended after successful operator CLI verification.

Read-only probes (``gh auth status``, ``vercel whoami``, …) do **not** enqueue
host-executor mutations; this block sets expectations without exposing secrets.
"""

from __future__ import annotations


def append_verify_vs_mutate_followup(body: str, *, verified: bool, provider_label: str) -> str:
    """Append a short Markdown section when ``verified`` is True."""
    if not verified:
        return body
    label = (provider_label or "CLI").strip()
    block = (
        f"### What this step did (and did not do)\n\n"
        f"✅ **{label} verification succeeded** — this turn ran **read-only** diagnostics.\n\n"
        "**It did not** write files, commit, push, or remove Vercel projects. Those use the "
        "**host executor** (separate queued jobs, each approved).\n\n"
        "**Examples of mutations** (queue via chat/UI, then approve):\n"
        "- `file_write` → `git_commit` → `git_push` (often three separate approvals)\n"
        "- `vercel_remove` with `vercel_yes: true` for a project slug\n\n"
        "Runbook: `docs/RUNBOOK_HOST_EXECUTOR_GIT_README.md` · "
        "Architecture: `docs/HANDOFF_OPERATOR_EXECUTION_AND_ORCHESTRATION.md` §11.8."
    )
    return body.rstrip() + "\n\n" + block

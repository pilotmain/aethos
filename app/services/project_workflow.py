# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Default stages for turning an idea into execution (AethOS execution system)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.project import Project
from app.services.project_registry import get_default_project, get_project_by_key

DEFAULT_IDEA_WORKFLOW: list[dict[str, str]] = [
    {
        "agent": "strategy",
        "stage": "validate",
        "label": "Validate problem, user, and demand",
    },
    {
        "agent": "marketing",
        "stage": "position",
        "label": "Define positioning and audience",
    },
    {
        "agent": "dev",
        "stage": "scope_mvp",
        "label": "Define MVP scope and technical plan",
    },
    {
        "agent": "qa",
        "stage": "acceptance",
        "label": "Define acceptance criteria and test plan",
    },
    {
        "agent": "ops",
        "stage": "deploy_plan",
        "label": "Choose deployment path and environment setup",
    },
]

_IT = frozenset({"it", "this", "that", "the", "a", "an"})


def resolve_project_key_for_workflow(
    text_after_verb: str,
    *,
    db: Session,
    active_project_key: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Resolves a project key from free text, active context, or default.
    Returns (key, err_message_if_missing).
    """
    raw = (text_after_verb or "").strip()
    w = raw.lower()
    if not w or w in _IT or w in ("it", "this", "that"):
        if (active_project_key or "").strip():
            return (active_project_key.strip().lower(), None)
        dp = get_default_project(db)
        if dp:
            return (dp.key, None)
        return (
            None,
            "No project is active. Say a project key (e.g. `barber-booking-app`) or set one with `/project set-default`.",
        )
    tok = w.split()[0] if w else ""
    if tok in _IT and len(w.split()) >= 2:
        tok = w.split()[1]
    key = re_slug_key(tok)
    p = get_project_by_key(db, key)
    if p is None:
        return (None, f"Unknown project `{key}`. Use /projects to list keys.")
    return (p.key, None)


def re_slug_key(s: str) -> str:
    t = (s or "").strip().lower().strip(".,!?:;`")
    return t


def _current_step(project: Project | None) -> dict[str, str] | None:
    idx = int(getattr(project, "workflow_step_index", 0) or 0)
    if 0 <= idx < len(DEFAULT_IDEA_WORKFLOW):
        return DEFAULT_IDEA_WORKFLOW[idx]
    return DEFAULT_IDEA_WORKFLOW[0] if DEFAULT_IDEA_WORKFLOW else None


def format_project_workflow(project: Project) -> str:
    lines: list[str] = [f"Workflow for **{project.display_name}**:\n"]
    for i, step in enumerate(DEFAULT_IDEA_WORKFLOW, start=1):
        agent = (step.get("agent") or "").title()
        label = step.get("label") or "—"
        lines.append(f"{i}. {agent} Agent — {label}")
    cur = _current_step(project) or {}
    if cur:
        ag = (cur.get("agent") or "").title()
        lines.append(f"\n**Current stage:** {ag}")
        n_agent = (cur.get("agent") or "strategy").lower()
        n_st = cur.get("stage") or "validate"
        lines.append(f"\n**Next command:**\n`@{n_agent} {n_st} {project.key}`")
    return "\n".join(lines)[:10_000]


# --- Agent-specific canned responses (no secrets; no cloud guesses) ---


def format_strategy_validate(
    project: Project,
) -> str:
    summary = (getattr(project, "idea_summary", None) or "").strip() or (
        f"{project.display_name} (no long summary saved; use the project key in chat)."
    )
    return (
        f"**Strategy review** for {project.display_name}:\n\n"
        f"**Target user (draft):** people who need what this product promises — refine from your audience.\n\n"
        f"**Core problem:** scheduling / trust / discovery — validate with 5 interviews.\n\n"
        f"**From your idea:** {summary[:900]}{'…' if len(summary) > 900 else ''}\n\n"
        f"**MVP (suggestion):** one narrow job-to-be-done, one flow, one measure of success.\n\n"
        f"**Risk:** scope creep; competitors; distribution.\n\n"
        f"**Next question:** is this mainly for **solo** practitioners or **teams**?"
    )[:10_000]


def format_marketing_position(project: Project) -> str:
    name = project.display_name
    return (
        f"**Positioning draft (AethOS / {name})**:\n\n"
        f"**For** busy independent operators who lose time on admin,\n"
        f"**{name}** is a focused tool\n"
        f"that **removes** scheduling friction\n"
        f"unlike a generic suite that adds noise.\n\n"
        f"**Tagline ideas:**\n"
        f"• Less admin, more work done.\n"
        f"• {name} — the essentials, without the bloat.\n"
    )[:10_000]


def format_dev_scope_mvp(
    project: Project,
) -> str:
    rp = (getattr(project, "repo_path", None) or "").strip()
    if not rp:
        k = project.key
        return (
            f"**MVP scope** needs a local repo to attach work to.\n\n"
            f"This project **does not** have a repo yet (idea stage).\n\n"
            f"Reply: **create repo for {k}**\n\n"
            f"(Creates `~/nexa-projects/{k}` on the host **after** you `approve` the queued job.)"
        )[:10_000]
    return (
        f"**MVP scope** for {project.display_name} (`{project.key}`):\n\n"
        f"• Auth (when needed for your threat model)\n"
        f"• Core happy-path feature\n"
        f"• Minimal admin / settings\n"
        f"• One integration you truly need (e.g. email or SMS)\n"
        f"• Basic tests on the main flow\n\n"
        f"**Repo:** `{rp}`\n"
        f"Next: run a real dev task in this project from chat."
    )[:10_000]

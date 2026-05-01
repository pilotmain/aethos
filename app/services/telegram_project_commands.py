"""Text handlers for /projects and /project (multi-project command center)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.dev_tools.registry import get_dev_tool
from app.services.project_registry import (
    create_project_mvp,
    get_project_by_key,
    list_projects,
    project_environments,
    project_services,
    set_default_project,
)
from app.services.project_workflow import format_project_workflow


def format_projects_list(db: Session) -> str:
    rows = list_projects(db)
    if not rows:
        return "No projects configured. Use `/project add <key> <provider> <path>` (path must exist on the host)."
    lines: list[str] = ["**Configured projects:**\n"]
    for p in rows:
        pvd = f"`{p.provider_key}`"
        pje = f"`{p.default_environment or '?'}`"
        serv = ", ".join(project_services(p) or []) or "(none)"
        lines.append(
            f"• **{p.display_name}** (`{p.key}`)\n"
            f"  Provider: {pvd}  ·  Default env: {pje}\n"
            f"  Services: {serv}\n"
        )
    return "\n".join(lines)[:10_000]


def format_projects_list_for_user(db: Session, role: str) -> str:
    from app.services.user_capabilities import GUEST_PROJECTS, can_see_repo_paths_in_projects

    r = (role or "guest").strip()
    if r == "guest":
        return GUEST_PROJECTS
    if not can_see_repo_paths_in_projects(role) and r == "trusted":
        rows = list_projects(db)
        if not rows:
            return "No projects configured in this instance yet."
        lines: list[str] = ["Nexa projects (summary, no host paths on shared bots):\n"]
        for p in rows:
            lines.append(
                f"• {p.display_name} (`{p.key}`) — default env: {p.default_environment or '—'}\n"
            )
        return "\n".join(lines)[:10_000]
    return format_projects_list(db)


def format_one_project(db: Session, key: str, *, role: str = "owner") -> str:
    p = get_project_by_key(db, key)
    if p is None:
        return f"No enabled project with key `{key!r}`. See /projects"
    dft = "yes" if p.is_default else "no"
    serv = ", ".join(project_services(p) or []) or "(none)"
    envs = ", ".join(project_environments(p) or []) or "(none)"
    dtool = getattr(p, "preferred_dev_tool", None) or "—"
    dmode = getattr(p, "dev_execution_mode", None) or "autonomous_cli"
    from app.services.user_capabilities import GUEST_PROJECTS, can_see_repo_paths_in_projects

    r = (role or "owner").strip()
    if r == "guest":
        return GUEST_PROJECTS
    repo = f"`{p.repo_path or '—'}`" if can_see_repo_paths_in_projects(role) else "hidden on this access level"
    return (
        f"**{p.display_name}**\n"
        f"Key: `{p.key}`\n"
        f"Host repo path: {repo}\n"
        f"Provider: `{p.provider_key}`\n"
        f"Dev tool: `{dtool}`\n"
        f"Dev mode: `{dmode}`\n"
        f"Environments: {envs}\n"
        f"Services: {serv}\n"
        f"Default: {dft}"
    )[:8000]


def run_project_add(db: Session, key: str, provider: str, path: str) -> str:
    k = (key or "").strip().lower()
    pv = (provider or "").strip().lower()
    rp = (path or "").strip()
    if not k or not pv or not rp:
        return "Usage: `/project add <key> <provider> <repo_path>` (paths with spaces: not supported in MVP)."
    try:
        p = create_project_mvp(
            db,
            key=k,
            display_name=k,
            provider_key=pv,
            repo_path=rp,
        )
    except (ValueError, OSError) as e:
        return f"Could not add project: {e!s}"
    return f"Created project **{p.display_name}** (`{p.key}`) with provider `{p.provider_key}` and repo `{p.repo_path}`. "


def run_set_default(db: Session, key: str) -> str:
    p = set_default_project(db, key)
    if p is None:
        return f"Could not set default — no enabled project with key `{key!r}`."
    return f"Default project is now **{p.display_name}** (`{p.key}`)."


def set_project_dev_tool(db: Session, project_key: str, tool_key: str) -> str:
    project = get_project_by_key(db, project_key)

    if not project:
        return f"I don’t know project `{project_key}`."

    if not get_dev_tool(tool_key):
        return f"I don’t know dev tool `{tool_key}`. Try `/dev tools`."

    project.preferred_dev_tool = tool_key.strip().lower()
    db.add(project)
    db.commit()

    return f"Set {project.display_name} dev tool to `{tool_key}`."


def set_project_dev_mode(db: Session, project_key: str, mode: str) -> str:
    allowed = {"autonomous_cli", "ide_handoff", "github_pr", "manual_review"}

    project = get_project_by_key(db, project_key)

    if not project:
        return f"I don’t know project `{project_key}`."

    m = (mode or "").strip()
    if m not in allowed:
        return f"Unsupported mode `{m}`. Allowed: {', '.join(sorted(allowed))}"

    project.dev_execution_mode = m
    db.add(project)
    db.commit()

    return f"Set {project.display_name} dev mode to `{m}`."


def format_dev_workspace(db: Session) -> str:
    s = get_settings()
    root = s.nexa_workspace_root
    lines = [f"Workspace root: `{root}`\n", "Projects:"]
    for p in list_projects(db):
        rp = p.repo_path or "—"
        lines.append(f"— {p.key} → `{rp}`")
    if len(lines) == 2:
        lines.append("— (none)")
    return "\n".join(lines)[:10_000]


def format_project_workflow_cmd(db: Session, key: str) -> str:
    p = get_project_by_key(db, key)
    if p is None:
        return f"No enabled project with key `{key!r}`. See /projects"
    return format_project_workflow(p)

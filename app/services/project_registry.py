"""Read registered projects; resolve per-key and default. Used by Ops, Dev, Telegram."""

from __future__ import annotations

import json

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.project import Project


def get_project_by_key(db: Session, key: str | None) -> Project | None:
    if not (key or "").strip():
        return None
    k = key.strip().lower()
    st = select(Project).where(Project.key == k, Project.is_enabled == True)  # noqa: E712
    return db.scalars(st).first()


def get_default_project(db: Session) -> Project | None:
    st = select(Project).where(
        Project.is_default == True,  # noqa: E712
        Project.is_enabled == True,  # noqa: E712
    )
    return db.scalars(st).first()


def list_projects(db: Session) -> list[Project]:
    st = select(Project).where(Project.is_enabled == True).order_by(Project.display_name.asc())  # noqa: E712
    return list(db.scalars(st).all())


def list_project_keys(db: Session) -> list[str]:
    return [p.key for p in list_projects(db)]


def project_services(project: Project) -> list[str]:
    try:
        return list(json.loads(project.services_json or "[]"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def project_environments(project: Project) -> list[str]:
    try:
        return list(json.loads(project.environments_json or "[]"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return []


def set_default_project(db: Session, key: str) -> Project | None:
    p = get_project_by_key(db, key)
    if p is None:
        return None
    db.execute(update(Project).where(Project.is_default == True).values(is_default=False))  # noqa: E712
    p.is_default = True
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_project_mvp(
    db: Session,
    *,
    key: str,
    display_name: str,
    provider_key: str,
    repo_path: str,
) -> Project:
    k = key.strip().lower()
    if not k:
        raise ValueError("project key required")
    existing = get_project_by_key(db, k)
    if existing:
        raise ValueError(f"project {k!r} already exists")
    from app.core.config import get_settings

    s = get_settings()
    p = Project(
        key=k,
        display_name=display_name.strip() or k,
        provider_key=provider_key.strip() or "local",
        repo_path=repo_path.strip() or None,
        default_environment="staging",
        services_json='["api", "bot", "db", "worker"]',
        environments_json='["local", "staging", "production"]',
        is_default=False,
        is_enabled=True,
        preferred_dev_tool=s.nexa_default_dev_tool,
        dev_execution_mode=s.nexa_default_dev_mode,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_idea_project(
    db: Session,
    *,
    key: str,
    display_name: str,
    idea_summary: str,
) -> Project:
    """
    Project from idea intake: no repo yet; local provider; services empty until you define them.
    """
    k = key.strip().lower()
    if not k:
        raise ValueError("project key required")
    if get_project_by_key(db, k):
        raise ValueError(f"project {k!r} already exists")
    summ = (idea_summary or "")[:20_000]
    from app.core.config import get_settings

    s = get_settings()
    p = Project(
        key=k,
        display_name=(display_name or k).strip() or k,
        idea_summary=summ or None,
        workflow_step_index=0,
        repo_path=None,
        provider_key="local",
        default_environment="staging",
        services_json="[]",
        environments_json="[\"local\", \"staging\", \"production\"]",
        is_default=False,
        is_enabled=True,
        preferred_dev_tool=s.nexa_default_dev_tool,
        dev_execution_mode=s.nexa_default_dev_mode,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

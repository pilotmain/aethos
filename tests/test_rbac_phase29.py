"""Phase 29 — multi-tenant RBAC (organizations, invites, permissions)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.project.controller import ProjectController
from app.services.project.persistence import ProjectStore
from app.services.rbac.models import RoleType
from app.services.rbac.organization_service import OrganizationService


@pytest.fixture
def rbac_db(tmp_path: Path) -> Path:
    return tmp_path / "rbac.db"


def test_create_org_and_owner(rbac_db: Path) -> None:
    svc = OrganizationService(db_path=rbac_db)
    org = svc.create_organization("Acme Corp", "acme", "user-1")
    assert org.slug.startswith("acme")
    m = svc.get_member(org.id, "user-1")
    assert m is not None
    assert m.role == RoleType.OWNER
    assert svc.get_active_organization_id("user-1") == org.id


def test_invite_accept(rbac_db: Path) -> None:
    svc = OrganizationService(db_path=rbac_db)
    org = svc.create_organization("Beta", "beta", "alice")
    inv = svc.create_invite(org.id, "alice", role=RoleType.MEMBER)
    assert inv is not None
    assert svc.accept_invite(inv.id, "bob", user_name="Bob")
    assert svc.get_member(org.id, "bob") is not None


def test_permission_matrix(rbac_db: Path) -> None:
    svc = OrganizationService(db_path=rbac_db)
    org = svc.create_organization("Gamma", "gamma", "owner1")
    svc.add_member(org.id, "viewer1", RoleType.VIEWER, invited_by="owner1")
    assert svc.check_permission(org.id, "viewer1", "view_all")
    assert not svc.check_permission(org.id, "viewer1", "manage_members")


def test_project_org_filter(tmp_path: Path) -> None:
    store = ProjectStore(db_path=tmp_path / "mc.db")
    ctrl = ProjectController(project_store=store)
    p1 = ctrl.create_project(
        "A", "g", team_scope="chat1", organization_id="org-a"
    )
    p2 = ctrl.create_project(
        "B", "g", team_scope="chat1", organization_id="org-b"
    )
    listed = ctrl.list_projects("chat1", organization_id="org-a")
    ids = {p.id for p in listed}
    assert p1.id in ids
    assert p2.id not in ids
    legacy = ctrl.create_project("C", "g", team_scope="chat1")
    listed_b = ctrl.list_projects("chat1", organization_id="org-a")
    ids_b = {p.id for p in listed_b}
    assert legacy.id in ids_b

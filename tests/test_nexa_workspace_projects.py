"""Nexa workspace projects — labeled folders under approved roots / host work tree."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.services.conversation_context_service import get_or_create_context
from app.services.host_executor_intent import safe_relative_path
from app.services.workspace_registry import add_root
from app.services.nexa_workspace_project_registry import (
    active_project_relative_base,
    add_workspace_project,
    list_workspace_projects,
    merge_payload_with_project_base,
    remove_workspace_project,
    set_active_workspace_project,
)


@pytest.fixture()
def rooted_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    monkeypatch.chdir(tmp_path)
    uid = f"nxp_u_{uuid.uuid4().hex[:12]}"
    root = tmp_path.resolve()
    ensure_schema()
    db = SessionLocal()
    try:
        try:
            add_root(db, uid, str(root))
        except ValueError:
            pass
    finally:
        db.close()
    return root, uid


def test_add_list_remove_project(rooted_tmp: tuple[Path, str]) -> None:
    root, uid = rooted_tmp
    sub = root / "app"
    sub.mkdir()
    db = SessionLocal()
    try:
        with patch(
            "app.services.nexa_workspace_project_registry.default_work_root_path",
            return_value=root,
        ):
            row = add_workspace_project(db, uid, str(sub.resolve()), "My App", description="d")
            assert row.id > 0
            rows = list_workspace_projects(db, uid)
            assert len(rows) >= 1
            gone = remove_workspace_project(db, uid, row.id)
            assert gone is not None
            assert list_workspace_projects(db, uid) == []
    finally:
        db.close()


def test_active_project_updates_context(rooted_tmp: tuple[Path, str]) -> None:
    root, uid = rooted_tmp
    sub = root / "lib"
    sub.mkdir()
    db = SessionLocal()
    try:
        with patch(
            "app.services.nexa_workspace_project_registry.default_work_root_path",
            return_value=root,
        ):
            row = add_workspace_project(db, uid, str(sub.resolve()), "lib")
            cctx = get_or_create_context(db, uid, web_session_id="default")
            set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=row.id)
            db.refresh(cctx)
            assert cctx.active_project_id == row.id
            b = active_project_relative_base(db, uid, cctx)
            assert b == "lib"
            set_active_workspace_project(db, owner_user_id=uid, cctx=cctx, project_id=None)
            db.refresh(cctx)
            assert cctx.active_project_id is None
    finally:
        db.close()


def test_merge_payload_prefixes_paths(rooted_tmp: tuple[Path, str]) -> None:
    _root, _uid = rooted_tmp
    pl = {"host_action": "read_multiple_files", "relative_path": ".", "intel_analysis": True}
    out = merge_payload_with_project_base(pl, "lib")
    assert out["relative_path"] == "lib"
    assert safe_relative_path(out["relative_path"] or "")


def test_invalid_path_outside_roots_rejected(rooted_tmp: tuple[Path, str]) -> None:
    root, uid = rooted_tmp
    outside = root.parent / "other_nxp_vol"
    outside.mkdir(exist_ok=True)
    db = SessionLocal()
    try:
        with patch(
            "app.services.nexa_workspace_project_registry.default_work_root_path",
            return_value=root,
        ):
            with pytest.raises(ValueError, match="workspace|root|outside|work root"):
                add_workspace_project(db, uid, str(outside.resolve()), "bad")
    finally:
        db.close()

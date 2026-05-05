"""Workspace path resolution for QA scans."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_resolver import extract_path_hint_from_message, resolve_workspace_path


def test_resolve_explicit_existing_tmp(tmp_path: Path) -> None:
    p = tmp_path / "proj"
    p.mkdir()
    got = resolve_workspace_path(str(p), db=None, owner_user_id=None)
    assert got == p.resolve()


def test_extract_path_from_message(tmp_path: Path) -> None:
    p = tmp_path / "repo"
    p.mkdir()
    msg = f"Review vulnerabilities in {p}"
    assert extract_path_hint_from_message(msg) == str(p.resolve())


def test_resolve_remembers_workspace_root(db_session, tmp_path: Path, monkeypatch) -> None:
    from app.models.user_settings import NexaUserSettings
    from app.services.workspace_resolver import LAST_WORKSPACE_UI_KEY, resolve_workspace_path

    monkeypatch.delenv("NEXA_WORKSPACE_ROOT", raising=False)
    fav = tmp_path / "saved_ws"
    fav.mkdir()
    uid = "web_ws_resolve_test"
    db_session.merge(NexaUserSettings(user_id=uid, privacy_mode=None, ui_preferences={}))
    db_session.commit()

    row = db_session.get(NexaUserSettings, uid)
    assert row is not None
    merged = dict(row.ui_preferences or {})
    merged[LAST_WORKSPACE_UI_KEY] = str(fav.resolve())
    row.ui_preferences = merged
    db_session.commit()

    got = resolve_workspace_path(None, db=db_session, owner_user_id=uid)
    assert got == fav.resolve()


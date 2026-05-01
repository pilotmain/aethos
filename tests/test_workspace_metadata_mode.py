"""workspace_metadata.json defaults track regulated vs developer posture."""

from __future__ import annotations

from app.services.agent_runtime.defaults import default_workspace_metadata


def test_developer_metadata_flags() -> None:
    d = default_workspace_metadata(workspace_mode="developer")
    assert d["workspace_mode"] == "developer"
    assert d["regulated_domain"] is False
    assert "dev" in (d.get("approval_mode") or "").lower()


def test_regulated_metadata_flags() -> None:
    d = default_workspace_metadata(workspace_mode="regulated")
    assert d["workspace_mode"] == "regulated"
    assert d["regulated_domain"] is True

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 46A — end-to-end dev pipeline surface (branch, PR step, summary)."""

from __future__ import annotations

import subprocess

from app.core.config import get_settings
from app.models.dev_runtime import NexaDevRun
from app.services.dev_runtime.service import DEV_PIPELINE_SEQUENCE, run_dev_mission
from app.services.dev_runtime.workspace import register_workspace


def test_dev_pipeline_sequence_includes_pr() -> None:
    assert "pr" in DEV_PIPELINE_SEQUENCE
    assert DEV_PIPELINE_SEQUENCE[-1] == "pr"


def test_run_dev_mission_full_payload_keys(db_session, tmp_path, monkeypatch) -> None:
    repo = tmp_path / "p46_full"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    monkeypatch.setenv("NEXA_DEV_WORKSPACE_ROOTS", str(tmp_path.resolve()))
    get_settings.cache_clear()
    try:
        uid = f"p46_pipe_{__import__('uuid').uuid4().hex[:10]}"
        ws = register_workspace(db_session, uid, "full", str(repo))
        out = run_dev_mission(db_session, uid, ws.id, "Phase 46 pipeline smoke", auto_pr=False)
        assert out.get("ok") is True
        pipe = out.get("pipeline") or {}
        seq = pipe.get("sequence") or []
        assert "pr" in seq
        br = out.get("branch")
        assert br and str(br).startswith("nexa/run-")
        assert out.get("summary")
        assert "commit_quality" in out
        run = db_session.get(NexaDevRun, out["run_id"])
        rj = getattr(run, "result_json", None) or {}
        assert isinstance(rj, dict)
        assert rj.get("pipeline_summary") or rj.get("summary")
    finally:
        monkeypatch.delenv("NEXA_DEV_WORKSPACE_ROOTS", raising=False)
        get_settings.cache_clear()

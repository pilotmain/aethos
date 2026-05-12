# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""``host_action: chain`` — flag, allowlist, stop_on_failure (sync steps)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services import host_executor
from app.services.host_executor_chain import (
    chain_step_output_failed,
    merge_chain_step,
    parse_chain_inner_allowed,
)


class _BaseSettings:
    nexa_host_executor_enabled = True
    host_executor_work_root = ""
    host_executor_timeout_seconds = 120
    host_executor_max_file_bytes = 262_144
    nexa_host_executor_chain_enabled = False
    nexa_host_executor_chain_max_steps = 10
    nexa_host_executor_chain_allowed_actions = ""

    def __init__(self, root: Path) -> None:
        self.host_executor_work_root = str(root)


def test_parse_chain_inner_allowed_default() -> None:
    s = _BaseSettings(Path("/tmp"))
    assert "git_push" in parse_chain_inner_allowed(s)


def test_merge_chain_inherits_cwd() -> None:
    base = {"host_action": "chain", "cwd_relative": "subrepo"}
    step = {"host_action": "git_commit", "commit_message": "x"}
    m = merge_chain_step(base, step)
    assert m.get("cwd_relative") == "subrepo"


def test_chain_step_output_failed_heuristic() -> None:
    assert chain_step_output_failed("git push failed (exit 128)\n")
    assert not chain_step_output_failed("Wrote 3 bytes to README.md")


def test_chain_disabled_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    s = _BaseSettings(tmp_path)
    s.nexa_host_executor_chain_enabled = False
    with patch.object(host_executor, "get_settings", return_value=s):
        with pytest.raises(ValueError, match="Chain host actions are disabled"):
            host_executor.execute_payload(
                {
                    "host_action": "chain",
                    "actions": [{"host_action": "file_write", "relative_path": "a.txt", "content": "x"}],
                }
            )


def test_chain_rejects_invalid_inner_action(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    s = _BaseSettings(tmp_path)
    s.nexa_host_executor_chain_enabled = True
    with patch.object(host_executor, "get_settings", return_value=s):
        with pytest.raises(ValueError, match="not allowed in a chain"):
            host_executor.execute_payload(
                {
                    "host_action": "chain",
                    "actions": [{"host_action": "vercel_remove", "vercel_project_name": "x", "vercel_yes": True}],
                }
            )


def test_chain_runs_steps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "f.txt").write_text("1", encoding="utf-8")
    s = _BaseSettings(tmp_path)
    s.nexa_host_executor_chain_enabled = True
    with patch.object(host_executor, "get_settings", return_value=s):
        out = host_executor.execute_payload(
            {
                "host_action": "chain",
                "actions": [
                    {"host_action": "file_write", "relative_path": "chain.txt", "content": "ok"},
                ],
            }
        )
    assert "Step 1" in out
    assert "chain.txt" in out or "Wrote" in out
    assert (tmp_path / "chain.txt").read_text() == "ok"


def test_chain_stops_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    s = _BaseSettings(tmp_path)
    s.nexa_host_executor_chain_enabled = True
    orig = host_executor.execute_payload

    def shim(payload: dict, *, db=None, job=None) -> str:
        if payload.get("_nexa_chain_inner_step") and (payload.get("host_action") or "").lower() == "vercel_projects_list":
            return "vercel projects list failed (exit 1)\n"
        return orig(payload, db=db, job=job)

    with patch.object(host_executor, "get_settings", return_value=s):
        with patch.object(host_executor, "execute_payload", side_effect=shim):
            out = host_executor.execute_payload(
                {
                    "host_action": "chain",
                    "actions": [
                        {"host_action": "file_write", "relative_path": "a.md", "content": "x"},
                        {"host_action": "vercel_projects_list"},
                        {"host_action": "vercel_projects_list"},
                    ],
                    "stop_on_failure": True,
                }
            )
    assert "Step 1" in out
    assert "Step 2" in out
    assert "Stopped" in out
    assert "Step 3" not in out

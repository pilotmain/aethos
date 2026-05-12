# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""File vs directory host routing and local file intent (read /path)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.host_executor import execute_payload
from app.services.host_executor_intent import infer_host_executor_action
from app.services.local_file_intent import infer_local_file_request


def test_infer_host_file_read_only_for_file_under_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = str(tmp_path.resolve())
    f = tmp_path / "a.txt"
    f.write_text("x", encoding="utf-8")
    (tmp_path / "subd").mkdir()

    class S:
        host_executor_work_root = root

    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        p = infer_host_executor_action("read a.txt")
    assert p == {"host_action": "file_read", "relative_path": "a.txt"}
    with patch("app.services.host_executor_intent.get_settings", return_value=S()):
        d = infer_host_executor_action("read subd")
    assert d is None


def test_infer_local_simple_read_directory_clarifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    root = str(tmp_path.resolve())
    app_dir = tmp_path / "app"
    app_dir.mkdir()

    class S:
        host_executor_work_root = root

    with patch("app.services.local_file_intent.get_settings", return_value=S()):
        lf = infer_local_file_request(f"read {app_dir.resolve()}", default_relative_base=".")
    assert lf.matched and lf.clarification_message
    assert "is a folder" in (lf.clarification_message or "")
    assert lf.directory_read_hint
    assert lf.payload is None


def test_host_executor_file_read_friendly_dir_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    d = tmp_path / "d"
    d.mkdir()
    root = str(tmp_path.resolve())

    class S:
        host_executor_work_root = root
        nexa_host_executor_enabled = True
        host_executor_max_file_bytes = 1_000_000
        host_executor_read_multiple_max_files = 5

    with (
        patch("app.services.host_executor.get_settings", return_value=S()),
        pytest.raises(ValueError, match="folder, not a file"),
    ):
        execute_payload(
            {
                "host_action": "file_read",
                "relative_path": "d",
            }
        )

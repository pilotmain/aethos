# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.tools.runtime_files import file_write
from app.tools.runtime_workspace import workspace_list, workspace_search


def test_workspace_list_and_search(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    file_write("ws/needle.txt", "find the needle_token_xyz here")
    lst = workspace_list(max_depth=6)
    assert lst.get("tool") == "workspace_list"
    assert any("needle.txt" in str(x) for x in (lst.get("entries") or []))
    hits = workspace_search("needle_token_xyz")
    assert hits.get("count", 0) >= 1

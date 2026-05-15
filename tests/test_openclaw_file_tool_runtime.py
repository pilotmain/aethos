# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.tools.runtime_files import file_read, file_write


def test_file_write_and_read_roundtrip(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_HOME_DIR", str(tmp_path))
    w = file_write("parity/rt.txt", "hello-files")
    assert w.get("ok") is True
    r = file_read("parity/rt.txt")
    assert r.get("ok") is True
    assert "hello-files" in str(r.get("content") or "")

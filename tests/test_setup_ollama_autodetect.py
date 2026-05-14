# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unit tests for ``scripts/setup.py`` Ollama CLI detection (no subprocess to real ollama)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_setup_module():
    root = Path(__file__).resolve().parents[1]
    path = root / "scripts" / "setup.py"
    spec = importlib.util.spec_from_file_location("aethos_scripts_setup_test", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_ollama_cli_on_path_uses_shutil_which(monkeypatch):
    mod = _load_setup_module()

    monkeypatch.setattr(mod.shutil, "which", lambda _name: "/fake/ollama")
    assert mod.ollama_cli_on_path() is True

    monkeypatch.setattr(mod.shutil, "which", lambda _name: None)
    assert mod.ollama_cli_on_path() is False

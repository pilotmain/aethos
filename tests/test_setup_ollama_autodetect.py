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


def test_ollama_tags_include_model():
    mod = _load_setup_module()
    assert mod.ollama_tags_include_model(["qwen2.5:7b"], "qwen2.5:7b") is True
    assert mod.ollama_tags_include_model(["qwen2.5:7b:latest"], "qwen2.5:7b") is True
    assert mod.ollama_tags_include_model(["phi3:latest"], "qwen2.5:7b") is False


def test_ollama_get_tags_json_parses(monkeypatch):
    mod = _load_setup_module()

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return b'{"models":[{"name":"qwen2.5:7b"}]}'

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(mod.urllib.request, "urlopen", lambda *a, **k: _Resp())
    data = mod.ollama_get_tags_json(base_url="http://127.0.0.1:11434")
    assert isinstance(data, dict)
    assert mod.ollama_tags_model_names(base_url="http://127.0.0.1:11434") == ["qwen2.5:7b"]


def test_ollama_get_tags_json_none_on_unreachable(monkeypatch):
    mod = _load_setup_module()

    def _boom(*_a, **_k):
        raise mod.urllib.error.URLError("refused")

    monkeypatch.setattr(mod.urllib.request, "urlopen", _boom)
    assert mod.ollama_get_tags_json(base_url="http://127.0.0.1:11434") is None

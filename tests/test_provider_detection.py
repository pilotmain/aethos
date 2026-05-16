# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import shutil

import pytest

from app.providers.provider_detection import detect_cli_path


def test_detect_cli_path_unknown_provider() -> None:
    assert detect_cli_path("not_a_real_provider_xyz") is None


def test_detect_cli_path_uses_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: "/opt/bin/vercel")
    assert detect_cli_path("vercel") == "/opt/bin/vercel"

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 25 — aethos_cli status/features/helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from aethos_cli.cli_features import cmd_features
from aethos_cli.env_util import upsert_env_file


def test_features_reads_env_keys(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    env = root / ".env"
    upsert_env_file(
        env,
        {
            "NEXA_HOST_EXECUTOR_ENABLED": "true",
            "NEXA_SOCIAL_ENABLED": "false",
        },
    )
    monkeypatch.setattr("aethos_cli.cli_features._repo_root", lambda: root)
    assert cmd_features() == 0


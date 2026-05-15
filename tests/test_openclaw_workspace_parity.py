# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace / durable path parity — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §3."""

from __future__ import annotations

from app.core.paths import get_aethos_data_dir


def test_default_aethos_data_dir_leaf_is_data() -> None:
    assert get_aethos_data_dir().name == "data"

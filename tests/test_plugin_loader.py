# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.plugins.plugin_loader import load_all_plugins


def test_load_all_plugins() -> None:
    out = load_all_plugins()
    assert isinstance(out.get("manifests"), list)
    assert len(out["manifests"]) >= 5

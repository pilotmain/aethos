# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.marketplace.runtime_marketplace import list_marketplace_plugins


def test_catalog_includes_provider_targets() -> None:
    ids = {p.get("plugin_id") for p in list_marketplace_plugins()}
    assert "vercel-provider" in ids
    assert "github-provider" in ids

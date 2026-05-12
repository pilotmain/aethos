# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from pathlib import Path

from app.services.skills.marketplace import can_install_entry, load_catalog


def test_catalog_loads_default() -> None:
    rows = load_catalog()
    assert isinstance(rows, list)
    if rows:
        ok, errs = can_install_entry(rows[0])
        assert isinstance(ok, bool)
        assert isinstance(errs, list)


def test_catalog_json_exists() -> None:
    root = Path(__file__).resolve().parents[1]
    p = root / "data" / "aethos_marketplace" / "catalog.json"
    assert p.is_file()

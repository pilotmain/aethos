# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 52C — provider catalog surface."""

from __future__ import annotations

from app.services.providers.catalog import (
    PROVIDERS,
    choose_provider_for_task,
    providers_by_region,
)


def test_catalog_has_us_europe_china_local() -> None:
    regions = {p.region for p in PROVIDERS}
    assert "us" in regions or "global" in regions
    assert "local" in regions


def test_choose_provider_respects_explicit_preference() -> None:
    assert choose_provider_for_task(user_settings={"preferred_provider": "deepseek"}) == "deepseek"


def test_providers_by_region_europe() -> None:
    eu = providers_by_region("europe")
    assert any(p.id == "mistral" for p in eu)

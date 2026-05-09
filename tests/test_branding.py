"""Tests for :mod:`app.core.branding` — product name and legacy ``Nexa`` substitution."""

from __future__ import annotations

import pytest

from app.core.branding import (
    access_restricted_body,
    display_product_name,
    substitute_legacy_product_name,
)
from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_branding_settings_cache() -> None:
    get_settings.cache_clear()
    display_product_name.cache_clear()
    yield
    get_settings.cache_clear()
    display_product_name.cache_clear()


def test_display_product_name_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AETHOS_BRAND_NAME", raising=False)
    get_settings.cache_clear()
    display_product_name.cache_clear()
    assert display_product_name() == "AethOS"


def test_substitute_legacy_product_name_word_boundary() -> None:
    out = substitute_legacy_product_name("Ask Nexa anything; Nexa_NEXA_env stays.")
    assert "Ask AethOS anything" in out
    assert "NEXA_env" in out


def test_access_restricted_uses_brand_not_hardcoded_nexa() -> None:
    body = access_restricted_body()
    assert "Nexa" not in body
    assert display_product_name() in body


def test_brand_override_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_BRAND_NAME", "MyBrand")
    assert display_product_name() == "MyBrand"

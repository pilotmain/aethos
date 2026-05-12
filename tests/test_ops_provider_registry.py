# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

import os

from app.services.ops.provider_registry import get_provider, list_provider_names
from app.services.ops.providers.railway import RailwayProvider


def test_list_includes_railway() -> None:
    n = list_provider_names()
    assert "railway" in n
    assert "local" in n


def test_get_railway() -> None:
    p = get_provider("railway")
    assert p is not None
    assert p.name == "railway"
    assert isinstance(p, RailwayProvider)


def test_get_unknown() -> None:
    assert get_provider("definitely_not_a_real_provider_ever") is None


def test_default_name_uses_env(monkeypatch) -> None:
    monkeypatch.setenv("NEXA_OPS_PROVIDER", "railway")
    p = get_provider(None)
    assert p is not None
    assert p.name == "railway"

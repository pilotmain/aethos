# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""ClawHub client falls back to bundled catalog when the remote registry fails."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.core.config import REPO_ROOT
from app.services.skills.clawhub_client import ClawHubClient


@pytest.fixture
def fallback_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        nexa_clawhub_enabled=True,
        nexa_clawhub_api_base="http://bad-registry.invalid.test/api/v1",
        nexa_clawhub_fallback_enabled=True,
        nexa_clawhub_fallback_catalog_path=str(
            REPO_ROOT / "data" / "aethos_marketplace" / "fallback_skills.json"
        ),
    )
    monkeypatch.setattr("app.services.skills.clawhub_client.get_settings", lambda: s)


def test_search_uses_fallback_when_remote_returns_404(fallback_settings, monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            class R:
                status_code = 404

                def json(self):
                    return {}

            return R()

    monkeypatch.setattr(
        "app.services.skills.clawhub_client.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )

    async def run():
        c = ClawHubClient()
        rows = await c.search_skills("git", 10)
        assert len(rows) >= 1
        assert any("git" in r.name.lower() for r in rows)

    asyncio.run(run())


def test_fallback_disabled_returns_empty_on_remote_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    s = SimpleNamespace(
        nexa_clawhub_enabled=True,
        nexa_clawhub_api_base="http://bad-registry.invalid.test/api/v1",
        nexa_clawhub_fallback_enabled=False,
        nexa_clawhub_fallback_catalog_path=str(
            REPO_ROOT / "data" / "aethos_marketplace" / "fallback_skills.json"
        ),
    )
    monkeypatch.setattr("app.services.skills.clawhub_client.get_settings", lambda: s)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, *args, **kwargs):
            class R:
                status_code = 404

                def json(self):
                    return {}

            return R()

    monkeypatch.setattr(
        "app.services.skills.clawhub_client.httpx.AsyncClient",
        lambda **kw: FakeClient(),
    )

    async def run():
        c = ClawHubClient()
        rows = await c.search_skills("git", 10)
        assert rows == []

    asyncio.run(run())

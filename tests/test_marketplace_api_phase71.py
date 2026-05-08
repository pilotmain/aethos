"""
Phase 71 — :mod:`app.api.routes.marketplace` smoke tests.

The marketplace router proxies the same :class:`ClawHubClient` /
:class:`SkillInstaller` the cron-token-gated ``/clawhub`` API uses, but exposes
them over the standard web auth flow so the Mission Control "Marketplace" panel
can call them from the browser. These tests assert:

* discovery (search / popular / installed) is reachable for any signed-in web
  user once the panel flag is on,
* mutating endpoints (install / uninstall / update) require Telegram-linked
  owner role,
* the panel-level kill switch (``NEXA_MARKETPLACE_PANEL_ENABLED``) returns 503
  even for the read-only routes,
* the response shapes match the typed client in ``web/lib/api/marketplace.ts``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.routes import marketplace as marketplace_module
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.skills.clawhub_models import (
    ClawHubSkillInfo,
    InstalledSkill,
    SkillSource,
    SkillStatus,
)


def _fake_skill(name: str = "demo_skill", version: str = "0.1.0") -> ClawHubSkillInfo:
    return ClawHubSkillInfo(
        name=name,
        version=version,
        description="Demo skill for tests",
        author="alice",
        publisher="community",
        tags=["demo", "test"],
        downloads=42,
        rating=4.5,
        updated_at=datetime.now(timezone.utc),
        signature=None,
        manifest_url="",
        archive_url="",
    )


def _fake_installed(name: str = "demo_skill") -> InstalledSkill:
    now = datetime.now(timezone.utc)
    return InstalledSkill(
        name=name,
        version="0.1.0",
        source=SkillSource.CLAWHUB,
        source_url=f"clawhub://{name}",
        installed_at=now,
        updated_at=now,
        status=SkillStatus.INSTALLED,
        publisher="community",
    )


@pytest.fixture()
def marketplace_client(monkeypatch):
    """Browser-style client: web auth resolves to a Telegram-style app_user_id."""

    uid = f"tg_{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid

    class _StubSettings:
        nexa_marketplace_panel_enabled = True

    monkeypatch.setattr(marketplace_module, "get_settings", lambda: _StubSettings())

    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def _stub_owner(monkeypatch, *, owner: bool) -> None:
    monkeypatch.setattr(
        marketplace_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: ("owner" if owner else "guest"),
    )


def test_search_proxies_clawhub_client(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client

    captured: dict[str, Any] = {}

    async def fake_search(self, query: str, limit: int = 20):  # noqa: ARG001
        captured["query"] = query
        captured["limit"] = limit
        return [_fake_skill("alpha"), _fake_skill("beta", "0.2.0")]

    monkeypatch.setattr(
        "app.api.routes.marketplace.ClawHubClient.search_skills", fake_search
    )

    r = client.get("/api/v1/marketplace/search", params={"q": "demo", "limit": 5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    names = [s["name"] for s in body["skills"]]
    assert names == ["alpha", "beta"]
    assert captured == {"query": "demo", "limit": 5}


def test_popular_proxies_clawhub_client(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client

    async def fake_popular(self, limit: int = 20):  # noqa: ARG001
        assert limit == 7
        return [_fake_skill("popular_one")]

    monkeypatch.setattr(
        "app.api.routes.marketplace.ClawHubClient.list_popular", fake_popular
    )

    r = client.get("/api/v1/marketplace/popular", params={"limit": 7})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["name"] for s in body["skills"]] == ["popular_one"]


def test_installed_proxies_installer(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.list_installed",
        lambda self: [_fake_installed("locally_installed")],
    )

    r = client.get("/api/v1/marketplace/installed")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["name"] for s in body["skills"]] == ["locally_installed"]
    assert body["skills"][0]["source"] == "clawhub"


def test_skill_info_404_when_missing(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client

    async def fake_info(self, name: str):  # noqa: ARG001
        assert name == "missing"
        return None

    monkeypatch.setattr(
        "app.api.routes.marketplace.ClawHubClient.get_skill_info", fake_info
    )

    r = client.get("/api/v1/marketplace/skill/missing")
    assert r.status_code == 404
    assert r.json()["detail"] == "skill_not_found"


def test_install_requires_owner(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=False)

    called = {"installed": False}

    async def fake_install(self, name, version="latest", *, force=False):
        called["installed"] = True
        return True, "ok", name

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.install", fake_install
    )

    r = client.post(
        "/api/v1/marketplace/install",
        json={"name": "demo_skill", "version": "latest"},
    )
    assert r.status_code == 403, r.text
    assert called["installed"] is False


def test_install_owner_calls_installer(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=True)

    async def fake_install(self, name, version="latest", *, force=False):
        assert name == "demo_skill"
        assert version == "latest"
        assert force is False
        return True, "ok", "demo_skill"

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.install", fake_install
    )

    r = client.post(
        "/api/v1/marketplace/install",
        json={"name": "demo_skill", "version": "latest"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["skill_name"] == "demo_skill"


def test_install_translates_known_failure_codes(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=True)

    async def fake_install(self, name, version="latest", *, force=False):
        return False, "publisher_not_trusted", None

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.install", fake_install
    )

    r = client.post(
        "/api/v1/marketplace/install",
        json={"name": "shady_skill", "version": "latest"},
    )
    assert r.status_code == 403
    assert r.json()["detail"] == "publisher_not_trusted"


def test_uninstall_requires_owner(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=False)

    r = client.post("/api/v1/marketplace/uninstall/demo_skill")
    assert r.status_code == 403


def test_uninstall_owner_calls_installer(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=True)

    async def fake_uninstall(self, name):
        assert name == "demo_skill"
        return True, "ok"

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.uninstall", fake_uninstall
    )

    r = client.post("/api/v1/marketplace/uninstall/demo_skill")
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "uninstalled"


def test_update_owner_propagates_force_flag(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client
    _stub_owner(monkeypatch, owner=True)

    captured: dict[str, Any] = {}

    async def fake_update(self, name, *, force=False):
        captured["name"] = name
        captured["force"] = force
        return True, "already_latest"

    monkeypatch.setattr(
        "app.api.routes.marketplace.SkillInstaller.update", fake_update
    )

    r = client.post("/api/v1/marketplace/update/demo_skill", params={"force": True})
    assert r.status_code == 200, r.text
    assert captured == {"name": "demo_skill", "force": True}


def test_panel_disabled_returns_503(marketplace_client, monkeypatch) -> None:
    client, _uid = marketplace_client

    class _DisabledSettings:
        nexa_marketplace_panel_enabled = False

    monkeypatch.setattr(
        marketplace_module, "get_settings", lambda: _DisabledSettings()
    )

    for path in (
        "/api/v1/marketplace/search?q=demo",
        "/api/v1/marketplace/popular",
        "/api/v1/marketplace/installed",
    ):
        r = client.get(path)
        assert r.status_code == 503, (path, r.text)
        assert "disabled" in r.json()["detail"].lower()

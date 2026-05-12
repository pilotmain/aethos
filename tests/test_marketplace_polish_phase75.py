# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 75 — Marketplace polish unit/integration tests.

Coverage:

* :class:`ClawHubSkillInfo` / :class:`InstalledSkill` — round-trip new
  fields (category, readme/changelog, skill_dependencies, permissions,
  available_version, update_checked_at) through :func:`to_dict` /
  :func:`row_to_installed_skill`. Old (pre-75) rows still load.
* :class:`ClawHubClient` — ``_parse_skill_info`` honours the new shape
  fallbacks (single-axis category falls back to first tag, lowercase
  permissions); ``list_featured`` returns ``[]`` on 404 / network error;
  ``search_skills`` accepts an optional ``category`` and applies a
  defensive client-side filter.
* :class:`SkillDependencyResolver` — leaves-first plan, cycle detection,
  missing-dep error, already-installed short-circuit, install_dependencies
  end-to-end with a fake installer.
* :class:`SkillInstaller.mark_update_checked` — stamps + clears
  ``available_version`` correctly; flips status between
  :class:`SkillStatus.OUTDATED` and :class:`SkillStatus.INSTALLED`.
* Executor sandbox — ``assert_permissions_allowed`` returns ``None`` when
  the manifest's permissions are a subset of the allowlist (or sandbox
  is off), and a structured deny string otherwise; per-skill timeout
  via :func:`asyncio.wait_for` actually fires.
* :class:`SkillUpdateChecker.scan_once` — counters for empty store,
  up-to-date skill, update-available skill, unreachable skill, and
  non-clawhub source skipped.
* New API endpoints — ``/marketplace/featured``,
  ``/marketplace/skill/{name}/details``, ``/marketplace/categories``,
  ``/marketplace/-/check-updates-now`` (owner-gated),
  ``/marketplace/-/capabilities``.
"""

from __future__ import annotations

import asyncio
import sys
import types
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import app.api.routes.marketplace as marketplace_module
from app.core.security import get_valid_web_user_id
from app.main import app
from app.services.skills import clawhub_client as clawhub_client_module
from app.services.skills import dependency_resolver as resolver_module
from app.services.skills import executor as executor_module
from app.services.skills import installer as installer_module
from app.services.skills import update_checker as update_checker_module
from app.services.skills.clawhub_models import (
    ClawHubSkillInfo,
    InstalledSkill,
    SkillSource,
    SkillStatus,
    row_to_installed_skill,
)
from app.services.skills.loader import SkillManifest


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# Models
# =============================================================================


def test_clawhub_skill_info_round_trip_includes_phase75_fields() -> None:
    info = ClawHubSkillInfo(
        name="x",
        version="1.0.0",
        description="d",
        author="a",
        publisher="p",
        tags=["development"],
        downloads=10,
        rating=4.0,
        updated_at=_now(),
        signature=None,
        manifest_url="",
        archive_url="",
        category="development",
        readme_url="https://x/readme",
        changelog_url="https://x/changelog",
        skill_dependencies=["dep_a"],
        permissions=["network"],
    )
    out = info.to_dict()
    assert out["category"] == "development"
    assert out["readme_url"] == "https://x/readme"
    assert out["changelog_url"] == "https://x/changelog"
    assert out["skill_dependencies"] == ["dep_a"]
    assert out["permissions"] == ["network"]


def test_installed_skill_round_trip_includes_phase75_fields() -> None:
    when = _now()
    row = InstalledSkill(
        name="x",
        version="1.0.0",
        source=SkillSource.CLAWHUB,
        publisher="p",
        installed_at=when,
        updated_at=when,
        available_version="1.1.0",
        update_checked_at=when,
        category="security",
    )
    persisted = row.to_row()
    revived = row_to_installed_skill(persisted)
    assert revived.available_version == "1.1.0"
    assert revived.update_checked_at is not None
    assert revived.category == "security"
    api = revived.to_dict()
    assert api["update_available"] is True
    assert api["available_version"] == "1.1.0"


def test_installed_skill_back_compat_loads_old_row_without_phase75_fields() -> None:
    when = _now().isoformat()
    legacy = {
        "name": "old",
        "version": "0.1.0",
        "source": "clawhub",
        "source_url": "clawhub://old",
        "installed_at": when,
        "updated_at": when,
        "status": "installed",
        "pinned_version": None,
        "publisher": "community",
    }
    revived = row_to_installed_skill(legacy)
    assert revived.available_version is None
    assert revived.update_checked_at is None
    assert revived.category == ""


# =============================================================================
# ClawHubClient — parse + list_featured + category filter
# =============================================================================


class _StubSettings:
    nexa_clawhub_api_base = "https://reg.example/api/v1"
    nexa_clawhub_enabled = True
    nexa_marketplace_panel_enabled = True
    nexa_marketplace_featured_panel_enabled = True
    nexa_marketplace_auto_update_skills = False
    nexa_marketplace_update_check_interval_seconds = 86400
    nexa_marketplace_sandbox_mode = True
    nexa_marketplace_skill_timeout_seconds = 30
    nexa_marketplace_skill_permissions_allowlist = ""
    nexa_clawhub_trusted_publishers = ""
    nexa_clawhub_require_install_approval = False
    nexa_clawhub_require_signature = False


@pytest.fixture
def settings(monkeypatch) -> _StubSettings:
    s = _StubSettings()
    monkeypatch.setattr(clawhub_client_module, "get_settings", lambda: s)
    monkeypatch.setattr(executor_module, "get_settings", lambda: s)
    monkeypatch.setattr(installer_module, "get_settings", lambda: s)
    monkeypatch.setattr(update_checker_module, "get_settings", lambda: s)
    monkeypatch.setattr(marketplace_module, "get_settings", lambda: s)
    return s


def test_parse_skill_info_falls_back_category_to_first_tag(settings) -> None:  # noqa: ARG001
    client = clawhub_client_module.ClawHubClient()
    info = client._parse_skill_info({
        "name": "demo",
        "version": "1.0.0",
        "tags": ["Productivity", "automation"],
    })
    assert info.category == "productivity"  # first tag, lowercased


def test_parse_skill_info_normalises_permissions_to_lowercase(settings) -> None:  # noqa: ARG001
    client = clawhub_client_module.ClawHubClient()
    info = client._parse_skill_info({
        "name": "demo",
        "version": "1.0.0",
        "permissions": ["NETWORK", " Filesystem_Write "],
    })
    assert info.permissions == ["network", "filesystem_write"]


def test_list_featured_returns_empty_on_404(settings, monkeypatch) -> None:  # noqa: ARG001
    client = clawhub_client_module.ClawHubClient()

    class _FakeResp:
        def __init__(self, status: int, body: Any) -> None:
            self.status_code = status
            self._body = body

        def json(self) -> Any:
            return self._body

    class _FakeAC:
        async def __aenter__(self) -> "_FakeAC":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_a: object, **_k: object) -> _FakeResp:
            return _FakeResp(404, {})

    monkeypatch.setattr(
        clawhub_client_module.httpx, "AsyncClient", lambda *a, **k: _FakeAC()
    )
    out = asyncio.run(client.list_featured(limit=5))
    assert out == []


def test_list_featured_parses_payload(settings, monkeypatch) -> None:  # noqa: ARG001
    client = clawhub_client_module.ClawHubClient()

    class _FakeResp:
        def __init__(self, status: int, body: Any) -> None:
            self.status_code = status
            self._body = body

        def json(self) -> Any:
            return self._body

    class _FakeAC:
        async def __aenter__(self) -> "_FakeAC":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_a: object, **_k: object) -> _FakeResp:
            return _FakeResp(
                200,
                {
                    "skills": [
                        {"name": "alpha", "version": "1.0.0", "category": "Marketing"},
                        {"name": "beta", "version": "2.0.0", "tags": ["security"]},
                    ]
                },
            )

    monkeypatch.setattr(
        clawhub_client_module.httpx, "AsyncClient", lambda *a, **k: _FakeAC()
    )
    out = asyncio.run(client.list_featured(limit=5))
    assert [s.name for s in out] == ["alpha", "beta"]
    assert out[0].category == "marketing"
    assert out[1].category == "security"  # fallback to first tag


def test_search_skills_applies_client_side_category_filter(settings, monkeypatch) -> None:  # noqa: ARG001
    client = clawhub_client_module.ClawHubClient()

    class _FakeResp:
        def __init__(self) -> None:
            self.status_code = 200

        def json(self) -> Any:
            return {
                "results": [
                    {"name": "a", "version": "1", "category": "development"},
                    {"name": "b", "version": "1", "category": "marketing"},
                ]
            }

    class _FakeAC:
        async def __aenter__(self) -> "_FakeAC":
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_a: object, **_k: object) -> _FakeResp:
            return _FakeResp()

    monkeypatch.setattr(
        clawhub_client_module.httpx, "AsyncClient", lambda *a, **k: _FakeAC()
    )
    filtered = asyncio.run(client.search_skills("anything", category="development"))
    assert [s.name for s in filtered] == ["a"]


# =============================================================================
# SkillDependencyResolver
# =============================================================================


@dataclass
class _FakeInstalled:
    name: str


@dataclass
class _FakeInstaller:
    """Tiny stand-in for SkillInstaller used by the resolver tests."""

    installed: list[_FakeInstalled] = field(default_factory=list)
    install_calls: list[tuple[str, str]] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    def list_installed(self) -> list[_FakeInstalled]:
        return list(self.installed)

    async def install(
        self, name: str, version: str, *, force: bool = False
    ) -> tuple[bool, str, str | None]:
        _ = force
        self.install_calls.append((name, version))
        if name in self.fail_for:
            return False, "download_failed", None
        self.installed.append(_FakeInstalled(name))
        return True, "ok", name


def _info(name: str, deps: list[str] | None = None) -> ClawHubSkillInfo:
    return ClawHubSkillInfo(
        name=name,
        version="1.0.0",
        description="",
        author="",
        publisher="community",
        tags=[],
        downloads=0,
        rating=0.0,
        updated_at=_now(),
        signature=None,
        manifest_url="",
        archive_url="",
        skill_dependencies=list(deps or []),
    )


def test_resolver_plan_orders_leaves_first(settings, monkeypatch) -> None:  # noqa: ARG001
    inst = _FakeInstaller()

    async def fake_get_info(self, name: str) -> ClawHubSkillInfo | None:
        _ = self
        graph = {
            "leaf_a": _info("leaf_a"),
            "leaf_b": _info("leaf_b"),
            "mid": _info("mid", ["leaf_a", "leaf_b"]),
        }
        return graph.get(name)

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_get_info
    )
    head = _info("head", ["mid"])
    resolver = resolver_module.SkillDependencyResolver(installer=inst)
    plan = asyncio.run(resolver.plan(head))
    names = [n.name for n in plan.nodes]
    assert names == ["leaf_a", "leaf_b", "mid", "head"]


def test_resolver_detects_cycle(settings, monkeypatch) -> None:  # noqa: ARG001
    inst = _FakeInstaller()

    async def fake_get_info(self, name: str) -> ClawHubSkillInfo | None:
        _ = self
        graph = {
            "x": _info("x", ["y"]),
            "y": _info("y", ["x"]),
        }
        return graph.get(name)

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_get_info
    )
    resolver = resolver_module.SkillDependencyResolver(installer=inst)
    with pytest.raises(resolver_module.SkillDependencyError) as excinfo:
        asyncio.run(resolver.plan(_info("x", ["y"])))
    assert excinfo.value.code == "cycle"


def test_resolver_missing_dependency_raises(settings, monkeypatch) -> None:  # noqa: ARG001
    inst = _FakeInstaller()

    async def fake_get_info(self, name: str) -> ClawHubSkillInfo | None:
        _ = self, name
        return None

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_get_info
    )
    resolver = resolver_module.SkillDependencyResolver(installer=inst)
    with pytest.raises(resolver_module.SkillDependencyError) as excinfo:
        asyncio.run(resolver.plan(_info("head", ["does_not_exist"])))
    assert excinfo.value.code == "missing"
    assert excinfo.value.name == "does_not_exist"


def test_resolver_skips_already_installed_dep(settings, monkeypatch) -> None:  # noqa: ARG001
    inst = _FakeInstaller(installed=[_FakeInstalled("dep_a")])

    async def fake_get_info(self, name: str) -> ClawHubSkillInfo | None:
        _ = self
        return {"head": _info("head", ["dep_a"])}.get(name)

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_get_info
    )
    resolver = resolver_module.SkillDependencyResolver(installer=inst)
    plan, newly = asyncio.run(
        resolver.install_dependencies(_info("head", ["dep_a"]))
    )
    assert newly == []
    assert any(n.already_installed and n.name == "dep_a" for n in plan.nodes)
    assert inst.install_calls == []


def test_resolver_install_dependencies_does_not_install_head(settings, monkeypatch) -> None:  # noqa: ARG001
    inst = _FakeInstaller()

    async def fake_get_info(self, name: str) -> ClawHubSkillInfo | None:
        _ = self
        return {
            "leaf": _info("leaf"),
            "head": _info("head", ["leaf"]),
        }.get(name)

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_get_info
    )
    resolver = resolver_module.SkillDependencyResolver(installer=inst)
    head = _info("head", ["leaf"])
    _, newly = asyncio.run(resolver.install_dependencies(head))
    assert newly == ["leaf"]
    assert ("head", "1.0.0") not in inst.install_calls
    assert ("leaf", "1.0.0") in inst.install_calls


# =============================================================================
# SkillInstaller.mark_update_checked
# =============================================================================


@pytest.fixture
def installer_with_one_skill(tmp_path, settings, monkeypatch) -> tuple[installer_module.SkillInstaller, str]:  # noqa: ARG001
    settings.nexa_clawhub_skill_root = str(tmp_path / "skills")  # type: ignore[attr-defined]
    inst = installer_module.SkillInstaller(skills_root=tmp_path / "skills")
    when = _now()
    inst._save_manifest([
        InstalledSkill(
            name="demo",
            version="1.0.0",
            source=SkillSource.CLAWHUB,
            publisher="community",
            installed_at=when,
            updated_at=when,
        )
    ])
    return inst, "demo"


def test_mark_update_checked_stamps_available_version(installer_with_one_skill) -> None:
    inst, name = installer_with_one_skill
    row = inst.mark_update_checked(name, available_version="1.1.0")
    assert row is not None
    assert row.available_version == "1.1.0"
    assert row.update_checked_at is not None
    assert row.status == SkillStatus.OUTDATED
    persisted = inst.list_installed()[0]
    assert persisted.available_version == "1.1.0"


def test_mark_update_checked_clears_when_available_matches_installed(installer_with_one_skill) -> None:
    inst, name = installer_with_one_skill
    inst.mark_update_checked(name, available_version="1.1.0")  # → OUTDATED
    row = inst.mark_update_checked(name, available_version="1.0.0")
    assert row is not None
    assert row.available_version is None
    assert row.status == SkillStatus.INSTALLED


def test_mark_update_checked_returns_none_for_missing(installer_with_one_skill) -> None:
    inst, _ = installer_with_one_skill
    assert inst.mark_update_checked("nope", available_version="9.9") is None


# =============================================================================
# Executor sandbox: permissions allowlist + timeout
# =============================================================================


def _manifest(name: str, *, perms: list[str] | None = None) -> SkillManifest:
    return SkillManifest(
        name=name,
        version="1.0.0",
        description="",
        author="",
        tags=[],
        input_schema={},
        output_schema={},
        execution_type="python",
        entry="entry.py",
        handler="run",
        dependencies=[],
        permissions=list(perms or []),
        source="local",
        base_dir=Path("/tmp"),
    )


def test_assert_permissions_allowed_passes_when_subset(settings) -> None:
    settings.nexa_marketplace_skill_permissions_allowlist = "network,filesystem_write"
    deny = executor_module.assert_permissions_allowed(_manifest("s", perms=["network"]))
    assert deny is None


def test_assert_permissions_allowed_denies_when_not_subset(settings) -> None:
    settings.nexa_marketplace_skill_permissions_allowlist = "network"
    deny = executor_module.assert_permissions_allowed(
        _manifest("s", perms=["network", "filesystem_write"])
    )
    assert deny is not None
    assert "filesystem_write" in deny


def test_assert_permissions_allowed_short_circuits_when_sandbox_off(settings) -> None:
    settings.nexa_marketplace_sandbox_mode = False
    settings.nexa_marketplace_skill_permissions_allowlist = ""
    deny = executor_module.assert_permissions_allowed(
        _manifest("s", perms=["network"])
    )
    assert deny is None


def test_execute_python_skill_enforces_timeout(settings, tmp_path) -> None:
    settings.nexa_marketplace_skill_timeout_seconds = 1  # very short
    settings.nexa_marketplace_sandbox_mode = True
    entry = tmp_path / "slow_entry.py"
    entry.write_text(
        "import asyncio\n"
        "async def run(**kwargs):\n"
        "    await asyncio.sleep(5)\n"
        "    return {'ok': True}\n"
    )
    skill = SkillManifest(
        name="slow",
        version="1.0.0",
        description="",
        author="",
        tags=[],
        input_schema={},
        output_schema={},
        execution_type="python",
        entry=str(entry),
        handler="run",
        dependencies=[],
        permissions=[],
        source="local",
        base_dir=tmp_path,
    )
    result = asyncio.run(executor_module.execute_python_skill(skill, {}))
    assert result.success is False
    assert result.error is not None and "timeout" in result.error.lower()


def test_execute_python_skill_runs_when_within_timeout(settings, tmp_path) -> None:
    settings.nexa_marketplace_skill_timeout_seconds = 5
    settings.nexa_marketplace_sandbox_mode = True
    entry = tmp_path / "fast_entry.py"
    entry.write_text("def run(**kwargs):\n    return {'ok': True}\n")
    skill = SkillManifest(
        name="fast",
        version="1.0.0",
        description="",
        author="",
        tags=[],
        input_schema={},
        output_schema={},
        execution_type="python",
        entry=str(entry),
        handler="run",
        dependencies=[],
        permissions=[],
        source="local",
        base_dir=tmp_path,
    )
    result = asyncio.run(executor_module.execute_python_skill(skill, {}))
    assert result.success is True
    assert result.output == {"ok": True}


# =============================================================================
# SkillUpdateChecker.scan_once
# =============================================================================


@dataclass
class _FakeUcInstaller:
    rows: list[InstalledSkill]
    marked: list[tuple[str, str | None]] = field(default_factory=list)

    def list_installed(self) -> list[InstalledSkill]:
        return list(self.rows)

    def mark_update_checked(
        self,
        name: str,
        *,
        available_version: str | None,
        checked_at: datetime | None = None,
    ) -> InstalledSkill | None:
        _ = checked_at
        self.marked.append((name, available_version))
        for r in self.rows:
            if r.name == name:
                r.available_version = available_version
                return r
        return None


@dataclass
class _FakeUcClient:
    catalog: dict[str, ClawHubSkillInfo | None]
    raise_for: set[str] = field(default_factory=set)

    async def get_skill_info(self, name: str) -> ClawHubSkillInfo | None:
        if name in self.raise_for:
            raise RuntimeError("registry exploded")
        return self.catalog.get(name)


def _row(name: str, version: str = "1.0.0", source: SkillSource = SkillSource.CLAWHUB) -> InstalledSkill:
    when = _now()
    return InstalledSkill(
        name=name,
        version=version,
        source=source,
        publisher="community",
        installed_at=when,
        updated_at=when,
    )


def test_update_checker_empty_store_returns_zero_counters(settings) -> None:  # noqa: ARG001
    inst = _FakeUcInstaller(rows=[])
    cli = _FakeUcClient(catalog={})
    checker = update_checker_module.SkillUpdateChecker(installer=inst, client=cli)  # type: ignore[arg-type]
    counters = asyncio.run(checker.scan_once())
    assert counters == {
        "scanned": 0,
        "up_to_date": 0,
        "updates_found": 0,
        "unreachable": 0,
        "skipped": 0,
    }


def test_update_checker_marks_update_when_remote_is_newer(settings) -> None:  # noqa: ARG001
    inst = _FakeUcInstaller(rows=[_row("demo", "1.0.0")])
    cli = _FakeUcClient(catalog={"demo": _info("demo")})  # _info() returns version "1.0.0"
    cli.catalog["demo"].version = "1.1.0"  # type: ignore[union-attr]
    checker = update_checker_module.SkillUpdateChecker(installer=inst, client=cli)  # type: ignore[arg-type]
    counters = asyncio.run(checker.scan_once())
    assert counters["updates_found"] == 1
    assert counters["up_to_date"] == 0
    assert ("demo", "1.1.0") in inst.marked


def test_update_checker_counts_unreachable_when_remote_returns_none(settings) -> None:  # noqa: ARG001
    inst = _FakeUcInstaller(rows=[_row("demo", "1.0.0")])
    cli = _FakeUcClient(catalog={"demo": None})
    checker = update_checker_module.SkillUpdateChecker(installer=inst, client=cli)  # type: ignore[arg-type]
    counters = asyncio.run(checker.scan_once())
    assert counters["unreachable"] == 1
    assert counters["updates_found"] == 0


def test_update_checker_skips_non_clawhub_source(settings) -> None:  # noqa: ARG001
    inst = _FakeUcInstaller(
        rows=[_row("local_skill", "1.0.0", source=SkillSource.LOCAL)]
    )
    cli = _FakeUcClient(catalog={})
    checker = update_checker_module.SkillUpdateChecker(installer=inst, client=cli)  # type: ignore[arg-type]
    counters = asyncio.run(checker.scan_once())
    assert counters["skipped"] == 1
    assert counters["scanned"] == 0
    assert inst.marked == []


def test_update_checker_swallows_get_skill_info_exception(settings) -> None:  # noqa: ARG001
    inst = _FakeUcInstaller(rows=[_row("boom", "1.0.0")])
    cli = _FakeUcClient(catalog={}, raise_for={"boom"})
    checker = update_checker_module.SkillUpdateChecker(installer=inst, client=cli)  # type: ignore[arg-type]
    counters = asyncio.run(checker.scan_once())
    assert counters["unreachable"] == 1


# =============================================================================
# API endpoints
# =============================================================================


def _override_user(uid: str) -> None:
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid


def _stub_owner(monkeypatch, *, owner: bool) -> None:
    monkeypatch.setattr(
        marketplace_module,
        "get_telegram_role_for_app_user",
        lambda _db, _uid: ("owner" if owner else "guest"),
    )


@pytest.fixture
def web_client(settings, monkeypatch):  # noqa: ARG001
    uid = f"tg_{uuid.uuid4().hex[:10]}"
    _override_user(uid)
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


def test_capabilities_endpoint_shape(settings, web_client) -> None:  # noqa: ARG001
    settings.nexa_marketplace_skill_permissions_allowlist = "network"
    client, _ = web_client
    r = client.get("/api/v1/marketplace/-/capabilities")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sandbox_mode"] is True
    assert body["skill_timeout_seconds"] == 30
    assert body["permissions_allowlist"] == ["network"]
    assert body["auto_update_skills"] is False


def test_featured_endpoint_returns_panel_enabled_flag(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    async def fake_featured(self, limit: int = 12):  # noqa: ARG001
        _ = self
        return [_info("alpha")]

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "list_featured", fake_featured
    )
    client, _ = web_client
    r = client.get("/api/v1/marketplace/featured")
    assert r.status_code == 200
    body = r.json()
    assert body["panel_enabled"] is True
    assert len(body["skills"]) == 1
    assert body["skills"][0]["name"] == "alpha"


def test_skill_details_endpoint_surfaces_documentation(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    detailed = ClawHubSkillInfo(
        name="x",
        version="1.0.0",
        description="d",
        author="a",
        publisher="p",
        tags=[],
        downloads=0,
        rating=0.0,
        updated_at=_now(),
        readme_url="https://x/readme",
        changelog_url="https://x/changelog",
        skill_dependencies=["dep_a"],
        permissions=["network"],
    )

    async def fake_info(self, name: str):  # noqa: ARG001
        _ = self
        return detailed if name == "x" else None

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_info
    )
    client, _ = web_client
    r = client.get("/api/v1/marketplace/skill/x/details")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["documentation"]["readme_url"] == "https://x/readme"
    assert body["dependencies"] == ["dep_a"]
    assert body["permissions"] == ["network"]


def test_skill_details_endpoint_404_when_missing(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    async def fake_info(self, name: str):  # noqa: ARG001
        _ = self, name
        return None

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "get_skill_info", fake_info
    )
    client, _ = web_client
    r = client.get("/api/v1/marketplace/skill/missing/details")
    assert r.status_code == 404


def test_categories_endpoint_dedupes_across_popular_and_featured(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    async def fake_popular(self, limit: int = 50):  # noqa: ARG001
        _ = self
        a = _info("a")
        a.category = "marketing"
        return [a]

    async def fake_featured(self, limit: int = 20):  # noqa: ARG001
        _ = self
        b = _info("b")
        b.category = "development"
        return [b]

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "list_popular", fake_popular
    )
    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "list_featured", fake_featured
    )
    client, _ = web_client
    r = client.get("/api/v1/marketplace/categories")
    assert r.status_code == 200
    assert sorted(r.json()["categories"]) == ["development", "marketing"]


def test_check_updates_now_requires_owner(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    _stub_owner(monkeypatch, owner=False)
    client, _ = web_client
    r = client.post("/api/v1/marketplace/-/check-updates-now")
    assert r.status_code == 403


def test_check_updates_now_calls_scan_once_for_owner(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    _stub_owner(monkeypatch, owner=True)

    captured: dict[str, int] = {}

    async def fake_scan(self) -> dict[str, int]:  # noqa: ARG001
        captured["called"] = 1
        return {
            "scanned": 3,
            "up_to_date": 2,
            "updates_found": 1,
            "unreachable": 0,
            "skipped": 0,
        }

    monkeypatch.setattr(
        update_checker_module.SkillUpdateChecker, "scan_once", fake_scan
    )
    client, _ = web_client
    r = client.post("/api/v1/marketplace/-/check-updates-now")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["counters"]["updates_found"] == 1
    assert captured.get("called") == 1


def test_search_endpoint_passes_optional_category(settings, web_client, monkeypatch) -> None:  # noqa: ARG001
    seen: dict[str, Any] = {}

    async def fake_search(self, query: str, limit: int = 20, *, category: str | None = None):  # noqa: ARG001
        seen["q"] = query
        seen["limit"] = limit
        seen["category"] = category
        return []

    monkeypatch.setattr(
        clawhub_client_module.ClawHubClient, "search_skills", fake_search
    )
    client, _ = web_client
    r = client.get("/api/v1/marketplace/search?q=hello&category=Marketing")
    assert r.status_code == 200
    assert seen["category"] == "marketing"


# Phase 75 — silence unused-import warning for `timedelta` / `types` / `sys`.
_ = (timedelta, types, sys)

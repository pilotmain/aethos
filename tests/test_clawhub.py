# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 17 — ClawHub marketplace client, installer manifest, API (cron auth)."""

from __future__ import annotations

import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.services.skills.clawhub_models import InstalledSkill, SkillSource, SkillStatus
from app.services.skills.installer import SkillInstaller


MINIMAL_YAML = """
name: test_skill
version: 0.1.0
description: t
author: a
tags: []
execution:
  type: python
  entry: x.py
  handler: run
"""


def test_skill_installer_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "skills"
    manifest = root / "installed.yaml"
    manifest.parent.mkdir(parents=True)
    row = InstalledSkill(
        name="my_skill",
        version="1.0.0",
        source=SkillSource.CLAWHUB,
        status=SkillStatus.INSTALLED,
        publisher="nexa",
    )
    inst = SkillInstaller(skills_root=root)
    inst._save_manifest([row])  # noqa: SLF001
    loaded = inst._load_manifest()  # noqa: SLF001
    assert len(loaded) == 1
    assert loaded[0].name == "my_skill"
    assert loaded[0].publisher == "nexa"


def test_trusted_publisher_filter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CLAWHUB_TRUSTED_PUBLISHERS", "nexa,openclaw")
    get_settings.cache_clear()
    inst = SkillInstaller(skills_root=tmp_path / "s")
    assert inst.is_trusted_publisher("nexa")
    assert not inst.is_trusted_publisher("unknown")


def test_install_from_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CLAWHUB_ENABLED", "true")
    monkeypatch.setenv("NEXA_CLAWHUB_TRUSTED_PUBLISHERS", "")
    get_settings.cache_clear()

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("skill.yaml", MINIMAL_YAML)
    payload = buf.getvalue()

    async def fake_info(nm: str):  # noqa: ARG001
        from app.services.skills.clawhub_models import ClawHubSkillInfo
        from datetime import datetime, timezone

        return ClawHubSkillInfo(
            name="test_skill",
            version="0.1.0",
            description="d",
            author="a",
            publisher="community",
            tags=[],
            downloads=0,
            rating=0.0,
            updated_at=datetime.now(timezone.utc),
        )

    async def fake_dl(nm: str, version: str = "latest"):  # noqa: ARG001
        return payload

    inst = SkillInstaller(skills_root=tmp_path / "skills")
    monkeypatch.setattr(inst.client, "get_skill_info", fake_info)
    monkeypatch.setattr(inst.client, "download_skill", fake_dl)

    import asyncio

    ok, msg, key = asyncio.run(inst.install("test_skill", "latest", force=True))
    assert ok and key == "test_skill"
    assert (tmp_path / "skills" / "test_skill" / "skill.yaml").is_file()


def test_clawhub_api_requires_cron_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "")
    get_settings.cache_clear()
    with TestClient(app) as c:
        r = c.get("/api/v1/clawhub/installed")
        assert r.status_code == 503


def test_clawhub_installed_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "tok_test")
    get_settings.cache_clear()

    monkeypatch.setattr(SkillInstaller, "list_installed", lambda self: [])

    with TestClient(app) as c:
        r = c.get("/api/v1/clawhub/installed", headers={"Authorization": "Bearer tok_test"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

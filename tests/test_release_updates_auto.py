# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Auto banner / GET /release/latest behaviors for release_updates."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import release_updates


def test_latest_release_parsed_with_newest_iso_date() -> None:
    src = """# Nexa Changelog

## Unreleased

### Added

* Draft

## 2026-01-01

### Added

* Older A

## 2026-04-27

### Added

* Web chat sessions

### Improved

* Wider responses
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(src)
        p = Path(f.name)
    try:
        rid = release_updates.get_current_release_id(changelog_path=p)
        assert rid == "2026-04-27"
        summary = release_updates.get_latest_release_summary(changelog_path=p)
        assert "Web chat sessions" in summary
        assert len(summary) <= 6
    finally:
        p.unlink(missing_ok=True)


def test_summary_is_short_plain_text() -> None:
    src = """## 2030-01-01

### Added

* **Bold** feat
* Plain [link](https://x.y/z)
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(src)
        p = Path(f.name)
    try:
        summary = release_updates.get_latest_release_summary(changelog_path=p)
        assert any("Bold" in x and "**" not in x for x in summary)
        assert any("link" in x.lower() or "Bold" in x for x in summary)
    finally:
        p.unlink(missing_ok=True)


def test_release_id_stable_across_calls() -> None:
    src = "## 2026-05-01\n\n### Added\n\n* One\n"
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(src)
        p = Path(f.name)
    try:
        a = release_updates.get_current_release_id(changelog_path=p)
        b = release_updates.get_current_release_id(changelog_path=p)
        assert a == b == "2026-05-01"
    finally:
        p.unlink(missing_ok=True)


def test_semver_section_release_id() -> None:
    src = """## Unreleased

## v1.4.2

### Added

* semver cut
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(src)
        p = Path(f.name)
    try:
        rid = release_updates.get_current_release_id(changelog_path=p)
        assert rid.startswith("v")
        assert "1.4.2" in rid
    finally:
        p.unlink(missing_ok=True)


@patch("app.core.security.get_settings")
def test_web_release_latest_requires_auth(mock_gs) -> None:
    mock_gs.return_value = type(
        "S",
        (),
        {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"},
    )()

    c = TestClient(app)
    r = c.get("/api/v1/web/release/latest")
    assert r.status_code == 401


@patch("app.core.security.get_settings")
def test_web_release_latest_returns_shape(mock_gs) -> None:
    mock_gs.return_value = type(
        "S",
        (),
        {"nexa_web_api_token": None, "nexa_web_origins": "http://localhost:3000"},
    )()

    c = TestClient(app)
    r = c.get("/api/v1/web/release/latest", headers={"X-User-Id": "web_smoke_1"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "release_id" in data and "items" in data and "full_text" in data
    assert isinstance(data["release_id"], str)
    assert isinstance(data["items"], list)
    assert isinstance(data["full_text"], str)


@patch("app.services.release_updates.get_release_updates", return_value="")
def test_empty_changelog_does_not_crash(_mock: object) -> None:
    assert release_updates.get_current_release_id() == ""
    assert release_updates.get_latest_release_summary() == []
    payload = release_updates.get_release_latest_for_web()
    assert payload["release_id"] == ""
    assert payload["items"] == []

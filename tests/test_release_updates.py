import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.services import release_updates


def test_get_latest_release_update_from_changelog_order() -> None:
    src = """# Nexa Changelog

## 2026-01-01

### Added

* Older

## 2026-04-27

### Added

* Web chat sessions
* Cost visibility

### Fixed

* Doctor report reliability
"""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(src)
        p = Path(f.name)
    try:
        info = release_updates.get_latest_release_update(changelog_path=p)
        assert info["release_id"] == "2026-04-27"
        assert "Web chat sessions" in info["bullets"]
        assert "Doctor report reliability" in info["bullets"] or "Doctor" in (info["bullets"][-1] or "")
    finally:
        p.unlink(missing_ok=True)


def test_get_release_updates_missing_file_safe() -> None:
    p = Path("/nonexistent/CHANGELOG_TEST_MISSING.md")
    text = release_updates.get_release_updates(changelog_path=p)
    assert text == ""


@patch("app.services.release_updates.get_release_updates", return_value="")
def test_latest_empty_changelog(_mock: object) -> None:
    info = release_updates.get_latest_release_update()
    assert info["release_id"] == ""
    assert info["bullets"] == []


def test_format_release_updates_for_chat_has_sections() -> None:
    t = release_updates.format_release_updates_for_chat()
    assert "Nexa Updates" in t
    assert "See CHANGELOG.md" in t


def test_web_release_notes_no_auth() -> None:
    c = TestClient(app)
    r = c.get("/api/v1/web/release-notes")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "release_id" in data
    assert "date" in data
    assert "title" in data
    assert "items" in data
    assert "full_text" in data
    assert isinstance(data["items"], list)

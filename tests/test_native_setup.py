"""Native setup wizard — .env upsert helper."""

from __future__ import annotations

from pathlib import Path

from nexa_cli.env_util import upsert_env_file


def test_upsert_env_replace_and_append(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    p.write_text("FOO=1\n# keep\nBAR=2\n", encoding="utf-8")
    upsert_env_file(p, {"FOO": "x", "BAZ": "three"})
    text = p.read_text(encoding="utf-8")
    assert "FOO=x" in text
    assert "BAR=2" in text
    assert "BAZ=" in text and "three" in text
    assert "# keep" in text


def test_upsert_env_quoting_spaces(tmp_path: Path) -> None:
    p = tmp_path / ".env"
    upsert_env_file(p, {"PATHY": "/tmp/my projects"})
    body = p.read_text(encoding="utf-8")
    assert "PATHY=" in body
    assert "my projects" in body

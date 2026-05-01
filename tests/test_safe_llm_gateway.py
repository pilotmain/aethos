"""Tests for :mod:`app.services.safe_llm_gateway`."""

from pathlib import Path

import pytest

from app.services import safe_llm_gateway as s


def test_sanitize_email_and_phone() -> None:
    raw = "Email john@example.com or call 555-123-4567"
    out = s.sanitize_text(raw)
    assert "john@example.com" not in out
    assert "555-123-4567" not in out
    assert "[EMAIL]" in out
    assert "[PHONE]" in out


def test_sanitize_api_key() -> None:
    raw = "OPENAI_API_KEY=sk-1234567890abcdefghijklmnop"
    out = s.sanitize_text(raw)
    assert "sk-1234567890" not in out
    assert "[API_KEY]" in out or "[SECRET]" in out or "[PASSWORD]" in out


def test_block_env_file() -> None:
    env_path = s.PROJECT_ROOT / ".env"
    assert s.is_safe_path(str(env_path)) is False
    assert s.is_safe_path(".env") is False


def test_allow_app_file() -> None:
    rel = "app/main.py"
    main_path = s.PROJECT_ROOT / rel
    if not main_path.is_file():
        pytest.skip("app/main.py not present in this checkout")
    assert s.is_safe_path(rel) is True
    assert s.is_safe_path(main_path) is True

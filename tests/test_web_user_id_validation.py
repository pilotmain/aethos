from __future__ import annotations

import pytest

from app.services.web_user_id import WEB_USER_ID_INVALID, validate_web_user_id


def test_tg_valid() -> None:
    assert validate_web_user_id("tg_123456789") == "tg_123456789"


def test_telegram_legacy_alias_normalized() -> None:
    assert validate_web_user_id("telegram_8666826080") == "tg_8666826080"


def test_telegram_colon_alias_normalized() -> None:
    assert validate_web_user_id("telegram:8666826080") == "tg_8666826080"


def test_web_demo_valid() -> None:
    assert validate_web_user_id("web_demo") == "web_demo"


def test_local_test_valid() -> None:
    assert validate_web_user_id("local_test") == "local_test"


def test_email_channel_id_valid() -> None:
    assert validate_web_user_id("em_a" + "b" * 7) == "em_abbbbbbb"


def test_slack_id_valid() -> None:
    assert validate_web_user_id("slack_U01ABCDEF12") == "slack_U01ABCDEF12"


def test_sms_wa_am_valid() -> None:
    assert validate_web_user_id("sms_15551234567") == "sms_15551234567"
    assert validate_web_user_id("wa_1234567890123") == "wa_1234567890123"
    assert validate_web_user_id("am_a" + "b" * 7) == "am_abbbbbbb"


def test_tg_pasted_token_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("tg_8666826080:AAG_fake_rejected_format")


def test_empty_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("")


def test_colon_in_web_prefix_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("web_a:b")


def test_spaces_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("tg_123 456")
    with pytest.raises(ValueError):
        validate_web_user_id("  tg_123")
    with pytest.raises(ValueError):
        validate_web_user_id("tg_123  ")


def test_too_long_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("web_" + "a" * 80)


def test_unsafe_rejected() -> None:
    with pytest.raises(ValueError):
        validate_web_user_id("tg_12%30")
    with pytest.raises(ValueError):
        validate_web_user_id("web_<>x")


def test_error_message_constant_has_no_injection() -> None:
    assert "AAG" not in WEB_USER_ID_INVALID
    assert ":" not in WEB_USER_ID_INVALID
    # callers must not interpolate client input into HTTP detail

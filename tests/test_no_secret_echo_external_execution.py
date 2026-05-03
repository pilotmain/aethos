"""P0 — credential flows never echo pasted material."""

from __future__ import annotations

from app.services.external_execution_credentials import format_secure_external_credential_setup


def test_secure_setup_template_never_contains_placeholder_secret() -> None:
    body = format_secure_external_credential_setup("railway")
    assert "your_token_here" in body.lower() or "your_token" in body.lower()
    assert "supersecret999" not in body


def test_input_guard_detects_railway_assign_without_echo() -> None:
    from app.services.input_secret_guard import user_message_contains_railway_credential_paste

    assert user_message_contains_railway_credential_paste(
        "RAILWAY_TOKEN=supersecret999_do_not_echo"
    )

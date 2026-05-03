"""P0 — scrub generic cloud-login refusal when user claims local CLI auth."""

from __future__ import annotations

from app.services.external_execution_session import scrub_generic_login_refusal_when_local_auth_claimed


def test_scrub_replaces_cannot_login_coaching() -> None:
    bad = (
        "I cannot log into your cloud provider (e.g. Railway) from this session. "
        "I can guide you — paste the output of railway whoami."
    )
    fixed = scrub_generic_login_refusal_when_local_auth_claimed(
        bad,
        "already authenticated, try for yourself",
    )
    assert "bounded read-only" in fixed.lower()
    assert "cannot log in" not in fixed.lower()


def test_scrub_unchanged_when_no_local_auth_claim() -> None:
    msg = "I cannot log into Railway without credentials."
    fixed = scrub_generic_login_refusal_when_local_auth_claimed(msg, "what is railway")
    assert fixed == msg


def test_scrub_unchanged_when_reply_not_generic_refusal() -> None:
    ok = "Here is the stack trace from your last deploy."
    fixed = scrub_generic_login_refusal_when_local_auth_claimed(ok, "already authenticated")
    assert fixed == ok

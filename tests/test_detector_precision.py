"""Phase 18 — detector precision (ingress vs egress)."""

from __future__ import annotations

from app.services.privacy_firewall.detectors import detect_sensitive_data

_SAMPLE_JWT = (
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
    "dozjgNryP4J3jVmNHl0w5N_XmcLZE51xqBuOpmaTzZc"
)


def test_egress_long_digits_not_phone_pii() -> None:
    r = detect_sensitive_data("version id is 555123456789012345678901234567890", mode="egress")
    assert "phone" not in r["pii"]


def test_egress_hex_hash_not_secret() -> None:
    h = "a" * 32 + "b" * 32
    r = detect_sensitive_data(f"sha256={h}", mode="egress")
    assert "high_entropy_token" not in r["secrets"]


def test_egress_openai_sk_prefix_high_confidence() -> None:
    r = detect_sensitive_data("leaked sk-" + "x" * 22, mode="egress")
    assert "openai_key" in r["secrets"]
    assert r["confidence"] == "high"


def test_egress_real_email_flagged() -> None:
    r = detect_sensitive_data("contact leak@example.com today", mode="egress")
    assert "email" in r["pii"]
    assert r["confidence"] == "low"


def test_ingress_still_catches_loose_phone() -> None:
    r = detect_sensitive_data("call 5551234567890", mode="ingress")
    assert "phone" in r["pii"]


def test_egress_credit_card_requires_luhn() -> None:
    bad = "1234-5678-9012-3456"
    r_bad = detect_sensitive_data(f"card {bad}", mode="egress")
    assert "credit_card" not in r_bad["pii"]

    good = "4532-0151-1283-0366"
    r_ok = detect_sensitive_data(f"card {good}", mode="egress")
    assert "credit_card" in r_ok["pii"]


def test_egress_jwt_medium_confidence() -> None:
    r = detect_sensitive_data(_SAMPLE_JWT, mode="egress")
    assert "jwt" in r["secrets"]
    assert r["confidence"] == "medium"

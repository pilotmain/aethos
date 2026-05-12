# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Signed license token verification (Ed25519)."""

from __future__ import annotations

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.core.config import get_settings
from app.services.licensing.features import FEATURE_SANDBOX_ADVANCED, has_pro_feature
from app.services.licensing.verify import PREFIX, verify_license_token


def _make_token(payload: dict, priv: Ed25519PrivateKey) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = priv.sign(raw)
    return ".".join(
        [
            PREFIX,
            base64.urlsafe_b64encode(raw).decode("ascii").rstrip("="),
            base64.urlsafe_b64encode(sig).decode("ascii").rstrip("="),
        ]
    )


@pytest.fixture
def ed25519_pair():
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    return priv, pem


def test_verify_roundtrip(ed25519_pair) -> None:
    priv, pem = ed25519_pair
    tok = _make_token({"features": ["sandbox_advanced"], "exp": time.time() + 3600}, priv)
    out = verify_license_token(tok, public_key_pem=pem)
    assert out is not None
    assert "sandbox_advanced" in out["features"]


def test_has_pro_feature_positive(monkeypatch: pytest.MonkeyPatch, ed25519_pair) -> None:
    priv, pem = ed25519_pair
    tok = _make_token({"features": [FEATURE_SANDBOX_ADVANCED], "exp": time.time() + 3600}, priv)
    monkeypatch.setenv("NEXA_LICENSE_KEY", tok)
    monkeypatch.setenv("NEXA_LICENSE_PUBLIC_KEY_PEM", pem)
    get_settings.cache_clear()
    try:
        assert has_pro_feature(FEATURE_SANDBOX_ADVANCED) is True
    finally:
        monkeypatch.delenv("NEXA_LICENSE_KEY", raising=False)
        monkeypatch.delenv("NEXA_LICENSE_PUBLIC_KEY_PEM", raising=False)
        get_settings.cache_clear()


def test_has_pro_feature_no_key_by_default() -> None:
    assert has_pro_feature(FEATURE_SANDBOX_ADVANCED) is False

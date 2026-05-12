# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.credentials import SecretRef, read_secret, store_secret


def test_vault_roundtrip_no_secret_in_ref() -> None:
    ref = store_secret("k1", "ultra-secret-value", scope="u1")
    assert "ultra-secret" not in str(ref)
    assert ref.key_id
    out = read_secret(ref, purpose="test")
    assert out == "ultra-secret-value"

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_secrets import mask_secret, redact_env_for_display


def test_mask_secret_never_full_echo() -> None:
    tok = "sk-test-abcdefghijklmnopqrstuvwxyz"
    masked = mask_secret(tok)
    assert tok not in masked
    assert "…" in masked


def test_redact_env_for_display() -> None:
    out = redact_env_for_display({"API_BASE_URL": "http://127.0.0.1:8010", "NEXA_WEB_API_TOKEN": "secret123"})
    assert "secret123" not in out["NEXA_WEB_API_TOKEN"]

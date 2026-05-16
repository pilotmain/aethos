# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.frontend_contract_lock import build_frontend_backend_contract_lock


def test_frontend_contract_lock() -> None:
    out = build_frontend_backend_contract_lock()
    assert out["capabilities_version"]
    assert out["error_semantics"]["404"]

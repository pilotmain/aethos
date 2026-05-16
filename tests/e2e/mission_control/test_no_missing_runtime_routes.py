# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.frontend_contract_lock import FRONTEND_RUNTIME_PATHS, build_frontend_backend_contract_lock


def test_frontend_paths_mostly_registered() -> None:
    lock = build_frontend_backend_contract_lock()
    assert lock["locked"] is True or len(lock.get("missing_from_capabilities_registry") or []) <= 6

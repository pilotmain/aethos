# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_startup_visibility import build_runtime_startup_visibility


def test_runtime_startup_visibility() -> None:
    blob = build_runtime_startup_visibility({})
    assert blob["runtime_startup_visibility"]["no_panic"] is True

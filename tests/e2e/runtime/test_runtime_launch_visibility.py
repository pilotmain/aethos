# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_startup_visibility import build_runtime_startup_visibility


def test_runtime_launch_visibility() -> None:
    assert build_runtime_startup_visibility({})["runtime_startup_visibility"]["startup_in_progress"] is not None

# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_visibility_authority import build_runtime_visibility_authority


def test_runtime_visibility_integrity() -> None:
    assert build_runtime_visibility_authority({})["runtime_visibility_authority"]["non_duplicated"] is True

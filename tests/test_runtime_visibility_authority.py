# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_visibility_authority import build_runtime_visibility_authority


def test_runtime_visibility_authority() -> None:
    blob = build_runtime_visibility_authority({})
    assert blob["runtime_visibility_authority"]["authoritative"] is True

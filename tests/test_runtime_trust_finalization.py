# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_trust_finalization import build_runtime_trust_finalization


def test_runtime_trust_finalization() -> None:
    blob = build_runtime_trust_finalization({"launch_stabilized": True, "enterprise_runtime_governed": True})
    assert len(blob["runtime_trust_finalization"]["categories"]) == 7

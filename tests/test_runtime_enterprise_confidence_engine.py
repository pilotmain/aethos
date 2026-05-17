# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_enterprise_confidence_engine import build_runtime_enterprise_confidence_engine


def test_runtime_enterprise_confidence_engine() -> None:
    blob = build_runtime_enterprise_confidence_engine({"launch_stabilized": True, "enterprise_runtime_governed": True})
    assert len(blob["runtime_enterprise_confidence_engine"]["categories"]) == 7

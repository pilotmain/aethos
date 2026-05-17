# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_unified_narrative_engine import build_runtime_unified_narrative_engine


def test_runtime_unified_narrative_engine() -> None:
    blob = build_runtime_unified_narrative_engine({})
    assert blob["runtime_unified_narrative_engine"]["no_conflicting_narratives"] is True

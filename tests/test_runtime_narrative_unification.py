# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_narrative_unification import build_runtime_narrative_unification


def test_runtime_narrative_roles() -> None:
    out = build_runtime_narrative_unification({})
    roles = out["runtime_narrative_unification"]["roles"]
    assert roles.get("office") == "Operational command center"
    assert out["runtime_narrative_unification"]["coherent_operational_narrative"] is True

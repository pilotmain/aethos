# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.workspace_operational_memory import add_deliverable_relationship, relationships_for_deliverable


def test_deliverable_relationship_types() -> None:
    rid = add_deliverable_relationship(
        from_id="dlv_a",
        to_id="dlv_b",
        relationship="supersedes",
    )
    assert rid
    rels = relationships_for_deliverable("dlv_a")
    assert any(r.get("relationship") == "supersedes" for r in rels)

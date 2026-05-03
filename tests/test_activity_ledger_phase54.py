from __future__ import annotations

from app.services.activity_ledger.ledger import (
    append_event,
    events_snapshot,
    reset_chain_for_tests,
    verify_chain_integrity,
)


def test_chain_integrity() -> None:
    reset_chain_for_tests()
    append_event(event_type="file.write", actor="nexa", resource="/tmp/x", payload_summary={"bytes": 4})
    append_event(event_type="shell.run", actor="nexa", resource="pytest", payload_summary={})
    assert verify_chain_integrity()
    assert len(events_snapshot()) == 2

# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Autonomous dev loop polish: UX helpers, labels, health, commit guards."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from app.services.telegram_dev_ux import (
    compact_review_for_telegram,
    format_job_row_short,
    user_friendly_status,
)
from app.services.worker_heartbeat import HEARTBEAT_PATH, build_dev_health_report


def test_compact_review_trims() -> None:
    long = "A" * 5000
    c = compact_review_for_telegram(long, 3200)
    assert "trim" in c.lower() or "…" in c or len(c) < 4000
    assert len(c) < 5000


def test_status_labels_friendly() -> None:
    assert "approval" in user_friendly_status("waiting_approval").lower()


def test_format_job_row_short_uses_key_fields() -> None:
    j = SimpleNamespace(
        id=1,
        status="failed",
        title="x",
        tests_status="failed",
        branch_name="b",
        error_message="tests blew up",
    )
    s = format_job_row_short(j)
    assert "#1" in s
    assert "failed" in s
    assert "Tests:" in s or "Reason:" in s


def test_dev_health_reads_heartbeat(tmp_path, monkeypatch) -> None:
    p = tmp_path / "h.json"
    p.write_text(
        json.dumps(
            {
                "status": "alive",
                "last_seen": "2026-01-15T10:00:00Z",
                "current_job_id": 3,
            }
        ),
        encoding="utf-8",
    )
    with patch("app.services.worker_heartbeat.HEARTBEAT_PATH", p):
        r = build_dev_health_report()
    assert "Dev worker" in r
    assert "3" in r
    _ = HEARTBEAT_PATH  # module attribute still used by worker process


def test_process_approved_refuses_if_tests_failed_no_override() -> None:
    st: dict = {"em": ""}

    j = SimpleNamespace(
        id=1,
        worker_type="dev_executor",
        user_id="u1",
        status="approved_to_commit",
        tests_status="failed",
        override_failed_tests=False,
        payload_json={},
    )

    class Svc:
        def mark_failed(self, db, job, em, **kw):
            st["em"] = str(em)
            return job

    from app.services.aider_autonomous_loop import process_approved_to_commit

    out = process_approved_to_commit(
        None,  # noqa: ANN
        j,
        Svc(),  # type: ignore[arg-type]
        from_worker=True,
    )
    assert "Refusing" in (st.get("em") or "")
    assert out is not None

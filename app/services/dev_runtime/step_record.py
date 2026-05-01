"""Persist NexaDevStep rows with Phase 25 iteration metadata."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.dev_runtime import NexaDevStep


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_dev_step(
    db: Session,
    *,
    run_id: str,
    step_type: str,
    iteration: int | None = None,
    adapter: str | None = None,
    input_json: dict[str, Any] | None = None,
    output_json: dict[str, Any] | None = None,
    test_result: dict[str, Any] | None = None,
    command: str | None = None,
    output_text: str | None = None,
    artifact_json: dict[str, Any] | None = None,
) -> NexaDevStep:
    row = NexaDevStep(
        run_id=run_id,
        step_type=step_type,
        status="running",
        command=command,
        output=output_text,
        artifact_json=artifact_json,
        created_at=_utc_now(),
        iteration=iteration,
        adapter=adapter,
        input_json=input_json,
        output_json=output_json,
        test_result=test_result,
    )
    db.add(row)
    db.flush()
    return row


__all__ = ["create_dev_step"]

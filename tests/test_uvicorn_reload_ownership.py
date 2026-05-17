# SPDX-License-Identifier: Apache-2.0

from app.services.mission_control.runtime_uvicorn_process import (
    detect_uvicorn_process_kind,
    filter_api_process_rows,
)


def test_filter_reloader_parent() -> None:
    rows = [
        {"pid": 1, "command": "python -m uvicorn app.main:app --reload"},
        {"pid": 2, "command": "python -m uvicorn app.main:app"},
    ]
    filtered = filter_api_process_rows(rows)
    assert len(filtered) == 1
    assert filtered[0]["pid"] == 2


def test_detect_uvicorn_kind_cli() -> None:
    assert detect_uvicorn_process_kind() in ("other", "api_worker", "reloader_parent")

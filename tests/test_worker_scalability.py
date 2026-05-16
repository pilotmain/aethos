# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.services.mission_control.worker_scalability import list_worker_summaries


def test_worker_summaries_pagination() -> None:
    out = list_worker_summaries(None, page=1, page_size=8)
    assert "workers" in out
    assert out.get("page") == 1
    assert "pressure" in out

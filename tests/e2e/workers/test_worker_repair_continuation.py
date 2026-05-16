# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from app.runtime.worker_operational_memory import create_continuation


def test_continuation_created() -> None:
    cid = create_continuation(worker_id="w1", source_task_id="t1", reason="continue repair")
    assert cid.startswith("cont_")

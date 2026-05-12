# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Run async plugin skills from synchronous :func:`~app.services.host_executor.execute_payload`."""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
import logging
from typing import Any

from app.services.skills.plugin_registry import get_plugin_skill_registry

logger = logging.getLogger(__name__)


def run_plugin_skill_sync(skill_name: str, input_data: dict[str, Any]) -> str:
    """Execute a registered plugin skill and return user-facing text."""

    async def _run():
        reg = get_plugin_skill_registry()
        return await reg.execute_skill(skill_name, input_data)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        result = asyncio.run(_run())
    else:

        def _thread_runner():
            return asyncio.run(_run())

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(_thread_runner).result(timeout=600)

    if result.success:
        try:
            blob = json.dumps(result.output, ensure_ascii=False, default=str)
        except TypeError:
            blob = str(result.output)
        return f"plugin_skill ok ({skill_name})\n{blob}"[:24_000]
    err = result.error or "skill failed"
    return f"plugin_skill failed ({skill_name}): {err}"[:24_000]


__all__ = ["run_plugin_skill_sync"]

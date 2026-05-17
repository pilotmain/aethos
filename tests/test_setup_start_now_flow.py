# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

from app.services.runtime.runtime_startup_orchestration import orchestrate_startup, prompt_startup_choice


def test_startup_save_only_skips_start() -> None:
    result = orchestrate_startup(choice="save_only")
    assert result["started"] is False
    assert "aethos start" in result["message"]


def test_prompt_startup_default_noninteractive() -> None:
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        choice = prompt_startup_choice()
    assert choice == "api_and_mission_control"

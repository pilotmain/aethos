# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import os
from unittest.mock import patch

from aethos_cli.ui import interactive_feature_toggle


def test_feature_multiselect_comma_list() -> None:
    opts = [
        ("Git", "git", ""),
        ("Browser", "browser", ""),
        ("Cron", "cron", ""),
        ("Social", "social", ""),
    ]
    with patch.dict(os.environ, {"NEXA_NONINTERACTIVE": "1"}, clear=False):
        chosen = interactive_feature_toggle("Features", opts, default_enabled=(1, 2))
    assert "git" in chosen
    assert "browser" in chosen


def test_feature_multiselect_help_mentions_recommended() -> None:
    from inspect import getsource

    src = getsource(interactive_feature_toggle)
    assert "recommended" in src
    assert "comma" in src.lower() or "commas" in src.lower()

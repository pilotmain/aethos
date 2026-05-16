# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_channels import configure_channel_choice


def test_channel_skip() -> None:
    updates: dict[str, str] = {}
    out = configure_channel_choice("skip", updates)
    assert out.get("channel") == "skip"
    assert not updates

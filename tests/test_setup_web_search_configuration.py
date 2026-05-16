# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_web_search import configure_web_search


def test_web_search_skip() -> None:
    updates: dict[str, str] = {}
    out = configure_web_search("skip", updates)
    assert out.get("provider") == "skip"

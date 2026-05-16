# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_wizard import _ollama_status


def test_ollama_status_returns_tuple() -> None:
    ok, msg, models = _ollama_status()
    assert isinstance(ok, bool)
    assert isinstance(msg, str)
    assert isinstance(models, list)

# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.core.config import print_local_service_urls


def test_print_local_service_urls_no_dashboard(capsys) -> None:
    print_local_service_urls()
    out = capsys.readouterr().out
    assert "Mission Control" in out
    assert "/dashboard" not in out
    assert "nexa_llm_provider" not in out

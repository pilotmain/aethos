# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import resolve_browser_launch_url, should_auto_open_browser


def test_browser_launch_requires_operational_runtime() -> None:
    assert resolve_browser_launch_url(truly_operational=False, mc_reachable=True) is None
    assert should_auto_open_browser(truly_operational=True, mc_reachable=True, api_reachable=True) is True

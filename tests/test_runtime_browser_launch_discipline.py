# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_orchestration import (
    resolve_browser_launch_url,
    should_auto_open_browser,
)


def test_browser_launch_office_when_operational() -> None:
    url = resolve_browser_launch_url(truly_operational=True, mc_reachable=True, first_run_onboarding_pending=False)
    assert url is not None
    assert url.endswith("/mission-control/office")


def test_browser_launch_onboarding_when_pending() -> None:
    url = resolve_browser_launch_url(truly_operational=True, mc_reachable=True, first_run_onboarding_pending=True)
    assert url is not None
    assert "/onboarding" in url


def test_browser_launch_blocked_when_not_operational() -> None:
    assert resolve_browser_launch_url(truly_operational=False, mc_reachable=True) is None
    assert should_auto_open_browser(truly_operational=False, mc_reachable=True, api_reachable=True) is False


def test_browser_launch_respects_no_browser_env(monkeypatch) -> None:
    monkeypatch.setenv("AETHOS_NO_BROWSER", "1")
    assert should_auto_open_browser(truly_operational=True, mc_reachable=True, api_reachable=True) is False

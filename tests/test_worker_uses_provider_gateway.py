# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Worker runner must route through provider gateway."""

from __future__ import annotations

import inspect

from app.services.workers import runner


def test_runner_invokes_call_provider_not_basic_tools() -> None:
    src = inspect.getsource(runner.run_agent)
    assert "call_provider" in src
    assert "prepare_external_payload" not in src
    assert "basic_tools" not in src


def test_runner_builds_provider_request_shape() -> None:
    src = inspect.getsource(runner.run_agent)
    assert "ProviderRequest" in src
    assert "read_artifacts" in src
    assert "write_artifact" in src
    assert '"inputs"' in src or "'inputs'" in src
    assert "db: Session" in src or ", db)" in src

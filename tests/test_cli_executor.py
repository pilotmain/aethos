"""CLI executor wraps subprocess with backend resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.cli_backends import reset_cli_backend_registry


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    reset_cli_backend_registry()
    yield
    reset_cli_backend_registry()


@patch("app.services.cli_executor.subprocess.run")
def test_run_cli_subprocess_uses_get_cli_command(
    mock_run: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    fake = tmp_path / "vercel"
    fake.write_text("#!/bin/sh\necho\n")
    fake.chmod(0o755)
    monkeypatch.setenv("NEXA_OPERATOR_CLI_VERCEL_ABS", str(fake))
    mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

    from app.services.cli_executor import run_cli_subprocess

    run_cli_subprocess("vercel", ["whoami"], timeout=5.0)
    mock_run.assert_called_once()
    args, _kw = mock_run.call_args
    assert args[0] == [str(fake.resolve()), "whoami"]

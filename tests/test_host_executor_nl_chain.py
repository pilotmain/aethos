"""NL → readme/commit/push chain (Week 2 v2)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.host_executor_nl_chain import try_infer_readme_push_chain_nl
from app.services.nexa_workspace_project_registry import merge_payload_with_project_base


class _AllOn:
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = True


class _NlOff:
    nexa_host_executor_enabled = True
    nexa_host_executor_chain_enabled = True
    nexa_nl_to_chain_enabled = False


def test_nl_disabled_returns_none() -> None:
    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_NlOff()):
        assert try_infer_readme_push_chain_nl("add readme and push") is None


def test_nl_matches_and_returns_chain() -> None:
    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_AllOn()):
        pl = try_infer_readme_push_chain_nl("Please add a README and push to remote")
    assert pl and pl.get("host_action") == "chain"
    assert len(pl.get("actions") or []) == 3
    assert pl["actions"][0].get("host_action") == "file_write"
    assert pl["actions"][0].get("relative_path") == "README.md"
    assert "docs:" in (pl["actions"][1].get("commit_message") or "")


def test_nl_extracts_saying_quoted() -> None:
    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_AllOn()):
        pl = try_infer_readme_push_chain_nl(
            'add readme saying "Service Stopped" and push'
        )
    assert pl and "Service Stopped" in (pl["actions"][0].get("content") or "")


def test_skips_explicit_json_host_payload() -> None:
    with patch("app.services.host_executor_nl_chain.get_settings", return_value=_AllOn()):
        pl = try_infer_readme_push_chain_nl(
            '{"host_action": "chain", "actions": []} add readme and push'
        )
    assert pl is None


def test_merge_project_base_with_chain() -> None:
    base = "pilot-command-center"
    pl = merge_payload_with_project_base(
        {
            "host_action": "chain",
            "actions": [
                {"host_action": "file_write", "relative_path": "README.md", "content": "x"},
                {"host_action": "git_commit", "commit_message": "docs: test"},
                {"host_action": "git_push"},
            ],
        },
        base,
    )
    assert pl["actions"][0]["relative_path"] == "pilot-command-center/README.md"
    assert pl["actions"][1].get("cwd_relative") == base
    assert pl["actions"][2].get("cwd_relative") == base

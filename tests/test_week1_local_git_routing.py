"""Local-git phrasing should not default to Railway bounded investigation."""

from __future__ import annotations

from app.services.intent_classifier import (
    looks_like_external_execution,
    _looks_like_local_git_workspace_without_hosted_provider,
)
from app.services.provider_router import should_skip_railway_bounded_path


def test_local_git_phrase_skips_railway_path() -> None:
    msg = "check this git in local and add a simple README about stopping the service"
    assert should_skip_railway_bounded_path(msg) is True


def test_local_git_not_skip_when_railway_named() -> None:
    msg = "check this git in local and also railway deploy logs"
    assert should_skip_railway_bounded_path(msg) is False


def test_looks_like_local_git_heuristic() -> None:
    assert _looks_like_local_git_workspace_without_hosted_provider(
        "check this git in local"
    )
    assert not _looks_like_local_git_workspace_without_hosted_provider(
        "check this git in local on railway"
    )


def test_looks_like_external_execution_false_for_local_git_only() -> None:
    assert not looks_like_external_execution(
        "check this git in local and add a README then push to remote"
    )

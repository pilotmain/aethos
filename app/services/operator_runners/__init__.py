"""Provider-scoped read-only CLIs for operator-mode orchestration (expandable)."""

from app.services.operator_runners.base import (
    TruthState,
    detect_provider_hints,
    format_operator_progress,
)
from app.services.operator_runners.github import run_github_operator_readonly
from app.services.operator_runners.local_dev import run_local_git_status
from app.services.operator_runners.railway import run_railway_operator_readonly
from app.services.operator_runners.vercel import run_vercel_operator_readonly

__all__ = [
    "TruthState",
    "detect_provider_hints",
    "format_operator_progress",
    "run_github_operator_readonly",
    "run_local_git_status",
    "run_railway_operator_readonly",
    "run_vercel_operator_readonly",
]

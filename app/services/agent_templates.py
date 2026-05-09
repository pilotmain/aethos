"""Predefined agent presets for Mission Control / orchestration (documentation + future UI).

These are **hints** for spawn payloads — the orchestration registry still validates
domain, name, and capabilities server-side.
"""

from __future__ import annotations

from typing import Any


AGENT_TEMPLATES: dict[str, dict[str, Any]] = {
    "developer": {
        "name": "developer_agent",
        "domain": "dev",
        "description": "Build and change code under registered workspace roots (host executor required).",
        "skills": [
            "code_generation",
            "file_operations",
            "command_execution",
            "git_operations",
        ],
        "capabilities": ["create", "modify", "execute", "test"],
        "system_prompt": (
            "You are a developer agent with access to the user's registered Nexa workspace roots. "
            "Prefer concrete actions: create files, run commands, and run tests via approved host jobs "
            "rather than only pasting code. Confirm before destructive actions (rm -rf, git push --force)."
        ),
    },
    "qa": {
        "name": "qa_agent",
        "domain": "qa",
        "description": "Testing and quality checks.",
        "skills": ["testing", "linting", "validation"],
        "capabilities": ["run_tests", "check_quality", "report_bugs"],
        "system_prompt": "You are a QA agent focused on tests, linting, and clear bug reports.",
    },
}


def list_template_keys() -> list[str]:
    return sorted(AGENT_TEMPLATES.keys())


def get_agent_template(key: str) -> dict[str, Any] | None:
    """Return a copy of the template or None."""
    t = AGENT_TEMPLATES.get((key or "").strip().lower())
    return dict(t) if t else None


__all__ = ["AGENT_TEMPLATES", "get_agent_template", "list_template_keys"]

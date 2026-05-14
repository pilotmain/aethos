# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Shared helpers for ``host_action: chain`` (permissions + execution)."""

from __future__ import annotations

from typing import Any

# Default inner steps — configurable via ``nexa_host_executor_chain_allowed_actions``.
DEFAULT_CHAIN_INNER_ALLOWED: frozenset[str] = frozenset(
    {"file_write", "git_commit", "git_push", "vercel_projects_list", "plugin_skill"}
)


def parse_chain_inner_allowed(settings: Any) -> frozenset[str]:
    raw = (getattr(settings, "nexa_host_executor_chain_allowed_actions", None) or "").strip()
    if not raw:
        return DEFAULT_CHAIN_INNER_ALLOWED
    parts = {p.strip().lower() for p in raw.split(",") if p.strip()}
    return frozenset(parts) if parts else DEFAULT_CHAIN_INNER_ALLOWED


def chain_actions_are_browser_plugin_skills(actions: Any) -> bool:
    """True when every step is ``plugin_skill`` with a ``browser_*`` skill (short NL automation chains)."""
    if not isinstance(actions, list) or not actions:
        return False
    for step in actions:
        if not isinstance(step, dict):
            return False
        if (step.get("host_action") or "").strip().lower() != "plugin_skill":
            return False
        sn = str(step.get("skill_name") or "").strip()
        if not sn.startswith("browser_") or len(sn) > 96 or "/" in sn or "\\" in sn:
            return False
        raw_inp = step.get("input")
        if raw_inp is not None and not isinstance(raw_inp, dict):
            return False
    return True


def merge_chain_step(chain_payload: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    """
    Inherit ``cwd_relative`` from the chain payload when a step omits it and the tool uses cwd
    (git, allowlisted run_command, Vercel CLI). File paths stay relative to the work root.
    """
    out = dict(step)
    cr_chain = str(chain_payload.get("cwd_relative") or "").strip()
    if not cr_chain:
        return out
    if str(out.get("cwd_relative") or "").strip():
        return out
    ha = (out.get("host_action") or "").strip().lower()
    if ha in (
        "git_status",
        "git_commit",
        "git_push",
        "run_command",
        "vercel_projects_list",
        "vercel_remove",
    ):
        out["cwd_relative"] = cr_chain
    return out


def chain_step_output_failed(text: str) -> bool:
    """Heuristic: host_executor returns user-facing text, not structured success flags."""
    t = (text or "").lower()
    if "failed (exit" in t:
        return True
    if "vercel remove failed" in t or "vercel projects list failed" in t:
        return True
    if "git push failed" in t or "git commit failed" in t or "git add failed" in t:
        return True
    return False

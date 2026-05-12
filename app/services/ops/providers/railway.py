# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from app.services.ops.providers.base import OpsProvider

if TYPE_CHECKING:
    from app.models.project import Project


def _log_tail(text: str, n: int = 2000) -> str:
    t = (text or "").strip()
    if not t:
        return "(no output)"
    if len(t) > n:
        return t[-n:]
    return t


class RailwayProvider(OpsProvider):
    name: ClassVar[str] = "railway"
    key: ClassVar[str] = "railway"

    def _cwd(self, project: "Project") -> str:
        p = (project.repo_path or "").strip()
        if p:
            return str(Path(p).expanduser().resolve())
        from app.services.handoff_paths import PROJECT_ROOT

        return str(Path(PROJECT_ROOT).resolve())

    def _run(
        self,
        project: "Project",
        cmd: list[str],
        *,
        extra_env: dict[str, str] | None = None,
        timeout: int = 300,
    ) -> str:
        m = {**os.environ, **(extra_env or {}), "NEXA_OPS_CHILD": "1"}
        try:
            p = subprocess.run(  # noqa: S603
                cmd,
                cwd=self._cwd(project),
                text=True,
                capture_output=True,
                timeout=timeout,
                env=m,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"(AethOS Railway: {e!s})"[:2000]
        out = p.stdout or ""
        if p.stderr:
            out = (out + "\nSTDERR:\n" + p.stderr).strip()
        if p.returncode not in (0,):
            return f"exit {p.returncode}\n" + (out or "")[:6000]
        return out or "(success, empty stdout)"

    def _env_for(self, target: str) -> dict[str, str] | None:
        t = (target or "staging").lower()
        m: dict[str, str] = {}
        if t in ("production", "prod", "pro"):
            val = (os.environ.get("NEXA_OPS_RAILWAY_PROD", "") or "").strip()
            if val:
                m["RAILWAY_ENVIRONMENT"] = val
        else:
            val = (os.environ.get("NEXA_OPS_RAILWAY_STAGING", "") or "").strip()
            if val:
                m["RAILWAY_ENVIRONMENT"] = val
        return m or None

    def execute(
        self,
        action_name: str,
        project: "Project",
        payload: dict[str, Any],
    ) -> str:
        pld = dict(payload or {})
        if action_name == "deploy_staging":
            e = pld.get("environment") or "staging"
            return _log_tail(
                self._run(
                    project,
                    ["railway", "up"],
                    extra_env=self._env_for(str(e)),
                    timeout=600,
                )
            )
        if action_name == "deploy_production":
            e = pld.get("environment") or "production"
            return _log_tail(
                self._run(
                    project,
                    ["railway", "up"],
                    extra_env=self._env_for(str(e)),
                    timeout=600,
                )
            )
        if action_name == "logs":
            svc = (str(pld.get("service") or "") or "").strip().lower()
            if svc in ("app", "web"):
                svc = "api"
            if svc in ("api", "bot", "worker"):
                r = self._run(project, ["railway", "logs", "--service", svc], timeout=120)
            else:
                r = self._run(project, ["railway", "logs"], timeout=120)
            return _log_tail(r, 2000)
        if action_name in ("status", "health"):
            r = self._run(project, ["railway", "status"], timeout=60)
            return _log_tail(r, 2000)
        if action_name == "restart_service":
            s = (str(pld.get("service") or "api") or "api").strip().lower()
            if s in ("app", "web"):
                s = "api"
            if s in ("api", "bot", "worker"):
                r = self._run(project, ["railway", "restart", s], timeout=300)
            else:
                r = self._run(project, ["railway", "restart"], timeout=300)
            return _log_tail(r, 2000)
        if action_name == "rollback":
            return self._rollback_msg()
        if action_name == "set_env_var":
            return "AethOS: use your Railway dashboard to change env vars (not executed here)."
        return f"AethOS: action `{action_name}` is not implemented for the Railway provider."

    def _rollback_msg(self) -> str:
        return (
            "AethOS: Railway has no one-size automated rollback in this path. Use the dashboard "
            "(Deployments → previous) for this project’s service."
        )

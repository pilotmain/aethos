from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from app.services.ops.providers.base import OpsProvider

if TYPE_CHECKING:
    from app.models.project import Project

_SERVICES: frozenset[str] = frozenset(
    {
        "api",
        "bot",
        "worker",
        "db",
        "postgres",
        "redis",
        "app",
        "all",
    }
)


def _log_tail(text: str, n: int = 3000) -> str:
    t = (text or "").strip()
    if not t:
        return "(no output)"
    if len(t) > n:
        return t[-n:]
    return t


class LocalDockerProvider(OpsProvider):
    name: ClassVar[str] = "local_docker"
    key: ClassVar[str] = "local_docker"

    def _root(self, project: "Project") -> str:
        p = (project.repo_path or "").strip()
        if p:
            return str(Path(p).expanduser().resolve())
        from app.services.handoff_paths import PROJECT_ROOT

        return str(Path(PROJECT_ROOT).resolve())

    def _compose_file(self, project: "Project") -> Path | None:
        cf = (os.environ.get("NEXA_OPS_DOCKER_COMPOSE") or "").strip()
        if cf and Path(cf).is_file():
            return Path(cf).resolve()
        c = Path(self._root(project)) / "docker-compose.yml"
        return c if c.is_file() else None

    def _base(self, project: "Project") -> list[str]:
        f = self._compose_file(project)
        if f is not None:
            return ["docker", "compose", "-f", str(f)]
        return ["docker", "compose"]

    def _run(self, project: "Project", cmd: list[str], timeout: int = 300) -> str:
        m = {**os.environ, "NEXA_OPS_CHILD": "1"}
        try:
            p = subprocess.run(  # noqa: S603
                cmd,
                cwd=self._root(project),
                text=True,
                capture_output=True,
                timeout=timeout,
                env=m,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return f"(local_docker: {e!s})"[:2000]
        out = (p.stdout or "") + (("\nSTDERR:\n" + p.stderr) if p.stderr else "")
        if p.returncode not in (0,):
            return f"exit {p.returncode}\n" + (out or "")[:4000]
        return out or "(success, empty output)"

    def execute(
        self,
        action_name: str,
        project: "Project",
        payload: dict[str, Any],
    ) -> str:
        pld = dict(payload or {})
        base = self._base(project)
        if action_name == "logs":
            s = (str(pld.get("service") or "api") or "api").lower()
            if s in ("app", "web"):
                s = "api"
            if s in ("db", "postgres"):
                s = "db"
            if s not in _SERVICES:
                s = "api"
            if s in ("all",):
                return _log_tail(
                    self._run(project, base + ["logs", "--tail", "100"], timeout=90),
                )
            return _log_tail(
                self._run(
                    project,
                    base + ["logs", s, "--tail", "100"],
                    timeout=90,
                )
            )
        if action_name in ("status", "health"):
            return _log_tail(self._run(project, base + ["ps"], timeout=60))
        if action_name == "restart_service":
            s = (str(pld.get("service") or "") or "").strip().lower()
            if s in ("app", "web"):
                s = "api"
            if not s:
                raise ValueError("Service is required for local docker restart.")
            return _log_tail(
                self._run(project, base + ["restart", s], timeout=120),
            )
        if action_name in ("deploy_staging", "deploy_production"):
            return _log_tail(
                self._run(project, base + ["up", "-d", "--build"], timeout=600),
            )
        if action_name == "rollback":
            return (
                "Nexa: `local_docker` has no single-command rollback. Pin images or use your runbook."
            )
        if action_name == "set_env_var":
            return "Nexa: set env in `.env` on the host; not applied from chat."
        return f"Nexa: action `{action_name}` is not available for the local_docker provider."

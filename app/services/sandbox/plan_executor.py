# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Execute allowlisted, user-approved sandbox plans under a single workspace root."""

from __future__ import annotations

import logging
import shlex
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.sandbox.action_allowlist import validate_plan_actions

logger = logging.getLogger(__name__)


class SandboxExecutor:
    """Bounded execution with pre-backup for write_file targets and rollback on any failure."""

    def __init__(
        self,
        workspace_root: str | Path,
        *,
        max_file_bytes: int,
        command_timeout_seconds: int,
    ) -> None:
        self.workspace = Path(workspace_root).expanduser().resolve()
        self.max_file_bytes = int(max_file_bytes)
        self.command_timeout_seconds = int(command_timeout_seconds)

    def _resolve_rel_file(self, rel: str) -> Path | None:
        p = (rel or "").strip().replace("\\", "/").lstrip("/")
        if not p or ".." in Path(p).parts:
            return None
        full = (self.workspace / p).resolve()
        try:
            full.relative_to(self.workspace)
        except ValueError:
            return None
        return full

    def _resolve_read_file_path(self, rel: str) -> Path | None:
        """Resolve paths for ``read_file``: workspace root, latest todo-style folder, then basename search."""
        direct = self._resolve_rel_file(rel)
        if direct is not None and direct.is_file():
            return direct
        raw = (rel or "").strip().replace("\\", "/").lstrip("/")
        if not raw or ".." in Path(raw).parts:
            return None
        from app.services.gateway.development_nl import _latest_todo_project

        todo = _latest_todo_project(self.workspace)
        if todo is not None:
            tp = (todo / raw).resolve()
            try:
                tp.relative_to(self.workspace)
            except ValueError:
                pass
            else:
                if tp.is_file():
                    return tp

        # Single path segment (e.g. ``styles.css``): bounded search under workspace.
        if "/" not in raw:
            name = Path(raw).name
            if not name:
                return None
            matches: list[Path] = []
            for i, cand in enumerate(self.workspace.rglob(name)):
                if i >= 200:
                    break
                if ".git" in cand.parts:
                    continue
                if not cand.is_file():
                    continue
                try:
                    cr = cand.resolve()
                    cr.relative_to(self.workspace)
                except ValueError:
                    continue
                matches.append(cr)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1 and todo is not None:
                tdr = todo.resolve()
                for m in matches:
                    try:
                        m.relative_to(tdr)
                        return m
                    except ValueError:
                        continue
                return matches[0]
        return None

    def execute_plan(self, plan: dict[str, Any], *, user_id: str) -> dict[str, Any]:
        _ = user_id
        ok_pre, errs = validate_plan_actions(
            plan,
            workspace_root=self.workspace,
            max_file_bytes=self.max_file_bytes,
        )
        if not ok_pre:
            return {
                "success": False,
                "rollback_performed": False,
                "results": [],
                "message": "Plan failed validation:\n" + "\n".join(f"- {e}" for e in errs),
            }

        backup_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + f"_{uuid.uuid4().hex[:8]}"
        backup_root = self.workspace / ".aethos_sandbox_backups" / backup_id
        actions = plan.get("actions") or []
        if not isinstance(actions, list):
            return {"success": False, "rollback_performed": False, "results": [], "message": "Invalid actions"}

        backups: dict[str, str] = {}  # relative posix path -> backup file path (as string)

        for act in actions:
            if not isinstance(act, dict):
                continue
            if str(act.get("type") or "") != "write_file":
                continue
            params = act.get("params") if isinstance(act.get("params"), dict) else {}
            rel = str(params.get("path") or "").strip().replace("\\", "/").lstrip("/")
            target = self._resolve_rel_file(rel)
            if target is None or not target.is_file():
                continue
            try:
                rel_key = target.relative_to(self.workspace).as_posix()
            except ValueError:
                continue
            dest = backup_root / rel_key
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, dest)
            backups[rel_key] = str(dest)

        results: list[dict[str, Any]] = []
        all_ok = True

        try:
            for act in actions:
                if not isinstance(act, dict):
                    continue
                typ = str(act.get("type") or "").strip()
                params = act.get("params") if isinstance(act.get("params"), dict) else {}
                if typ == "read_file":
                    rel = str(params.get("path") or "")
                    path = self._resolve_read_file_path(rel)
                    if path is None or not path.is_file():
                        results.append(
                            {
                                "action": typ,
                                "status": "failed",
                                "path": rel,
                                "error": f"not found (tried workspace and todo-style subfolders for {rel!r})",
                            }
                        )
                        all_ok = False
                        continue
                    data = path.read_text(encoding="utf-8", errors="replace")
                    if len(data) > 50_000:
                        data = data[:50_000] + "\n… [truncated]"
                    try:
                        rel_disp = path.relative_to(self.workspace).as_posix()
                    except ValueError:
                        rel_disp = rel
                    results.append({"action": typ, "status": "ok", "path": rel_disp, "preview": data})

                elif typ == "write_file":
                    rel = str(params.get("path") or "")
                    content = str(params.get("content") or "")
                    path = self._resolve_rel_file(rel)
                    if path is None:
                        results.append({"action": typ, "status": "failed", "path": rel, "error": "bad path"})
                        all_ok = False
                        continue
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                    results.append({"action": typ, "status": "ok", "path": rel})

                elif typ == "run_command":
                    cmd = str(params.get("command") or "").strip()
                    cwd_rel = str(params.get("cwd") or ".").strip() or "."
                    cwd = self._resolve_rel_file(cwd_rel)
                    if cwd is None or not cwd.is_dir():
                        results.append({"action": typ, "status": "failed", "error": "bad cwd"})
                        all_ok = False
                        continue
                    try:
                        argv = shlex.split(cmd)
                    except ValueError as e:
                        results.append({"action": typ, "status": "failed", "error": str(e)})
                        all_ok = False
                        continue
                    try:
                        proc = subprocess.run(
                            argv,
                            cwd=str(cwd),
                            capture_output=True,
                            text=True,
                            timeout=self.command_timeout_seconds,
                            shell=False,
                        )
                    except subprocess.TimeoutExpired:
                        results.append({"action": typ, "status": "failed", "error": "timeout"})
                        all_ok = False
                        continue
                    except OSError as e:
                        results.append({"action": typ, "status": "failed", "error": str(e)})
                        all_ok = False
                        continue
                    results.append(
                        {
                            "action": typ,
                            "status": "ok" if proc.returncode == 0 else "failed",
                            "command": cmd,
                            "returncode": proc.returncode,
                            "stdout": (proc.stdout or "")[:2000],
                            "stderr": (proc.stderr or "")[:2000],
                        }
                    )
                    if proc.returncode != 0:
                        all_ok = False

                elif typ == "open_browser":
                    url = str(params.get("url") or "").strip()
                    try:
                        import webbrowser

                        webbrowser.open(url)
                    except Exception as e:  # noqa: BLE001
                        results.append({"action": typ, "status": "failed", "url": url, "error": str(e)})
                        all_ok = False
                        continue
                    results.append({"action": typ, "status": "ok", "url": url})

        except Exception as e:  # noqa: BLE001
            logger.warning("sandbox.execute unexpected: %s", e, exc_info=True)
            all_ok = False
            results.append({"action": "internal", "status": "failed", "error": str(e)})

        if not all_ok:
            self._rollback(backup_root, backups)
            return {
                "success": False,
                "rollback_performed": bool(backups),
                "results": results,
                "message": "One or more actions failed; prior file states were restored where backed up.",
            }

        return {"success": True, "rollback_performed": False, "results": results, "backup_id": backup_id}

    def _rollback(self, backup_root: Path, backups: dict[str, str]) -> None:
        for rel_key, bak in backups.items():
            src = Path(bak)
            if not src.is_file():
                continue
            dst = self.workspace / rel_key
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            except OSError:
                logger.warning("sandbox.rollback failed for %s", rel_key, exc_info=True)


def format_sandbox_results(results: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for r in results:
        typ = str(r.get("action") or "?")
        st = str(r.get("status") or "?")
        if typ == "run_command":
            lines.append(f"- **{typ}** ({st}): `{str(r.get('command') or '')[:200]}` rc={r.get('returncode')}")
            if r.get("stderr"):
                lines.append(f"  stderr: `{str(r.get('stderr'))[:400]}`")
        elif typ in ("read_file", "write_file"):
            lines.append(f"- **{typ}** ({st}): `{str(r.get('path') or '')[:200]}`")
        elif typ == "open_browser":
            lines.append(f"- **{typ}** ({st}): `{str(r.get('url') or '')[:200]}`")
        else:
            lines.append(f"- **{typ}** ({st})")
    return "\n".join(lines) if lines else "(no steps)"

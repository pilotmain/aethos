"""Gateway NL: start scaffolded workspace apps (static todo bundle, optional Node backend, React)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.gateway.context import GatewayContext
from app.services.gateway.early_nl_host_actions import _workspace_root_for_nl
from app.services.host_executor_intent import parse_start_app_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations

# Matches default in ``app.services.execution_templates.todo_backend_node_bundle`` (``node server.js``).
_TODO_BACKEND_DEFAULT_PORT = 3847


def _discover_static_app_dirs(workspace: Path) -> list[Path]:
    if not workspace.is_dir():
        return []
    out: list[Path] = []
    for p in workspace.iterdir():
        if p.is_dir() and (p / "index.html").is_file():
            out.append(p)
    return out


def _discover_react_app_dirs(workspace: Path) -> list[Path]:
    if not workspace.is_dir():
        return []
    out: list[Path] = []
    for p in workspace.iterdir():
        pkg = p / "package.json"
        if not p.is_dir() or not pkg.is_file():
            continue
        try:
            blob = pkg.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        if "react-scripts" in blob or '"react"' in blob:
            out.append(p)
    return out


def _by_mtime(paths: list[Path]) -> list[Path]:
    return sorted(paths, key=lambda x: x.stat().st_mtime_ns, reverse=True)


def _pick_project(workspace: Path, parsed: dict[str, Any]) -> Path | None:
    kind = str(parsed.get("kind") or "")
    slug_q = str(parsed.get("slug") or "").strip().lower()
    static = _by_mtime(_discover_static_app_dirs(workspace))
    react = _by_mtime(_discover_react_app_dirs(workspace))

    if kind == "named" and slug_q:
        for bucket in (static, react):
            for p in bucket:
                n = p.name.lower()
                if n == slug_q or n == f"{slug_q}-app" or slug_q in n:
                    return p
        return None
    if kind == "todo":
        for p in static:
            if "todo" in p.name.lower():
                return p
        return static[0] if static else None
    if kind == "react":
        return react[0] if react else None
    if kind == "recent":
        for p in static:
            if (p / "backend" / "server.js").is_file():
                return p
        if static:
            return static[0]
        return react[0] if react else None
    return None


def try_start_built_app_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    """
    Privileged owners only (same gate as :mod:`early_nl_host_actions` React scaffold).

    Starts **npm start** for React apps, **node server.js** for our todo backend bundle,
    and best-effort opens root ``index.html`` in the default browser.
    """
    _ = db
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None

    parsed = parse_start_app_intent(raw)
    if not parsed:
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_auto_approve_owner", True)):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    root = Path(_workspace_root_for_nl()).expanduser().resolve()
    if not root.is_dir():
        return {
            "mode": "chat",
            "text": (
                f"**Workspace not found**\n\nExpected a directory at `{root}`. "
                "Set `NEXA_COMMAND_WORK_ROOT` (or host work root) and try again."
            ),
            "intent": "start_app_error",
            "host_executor": True,
        }

    proj = _pick_project(root, parsed)
    if proj is None:
        return {
            "mode": "chat",
            "text": (
                f"**No matching app** under `{root}`.\n\n"
                "Build one first — for example: **build a todo app** or "
                "**build a todo app with a database backend**."
            ),
            "intent": "start_app_error",
            "host_executor": True,
        }

    lines: list[str] = [f"🚀 **Starting `{proj.name}`**", ""]

    backend = proj / "backend" / "server.js"
    pkg = proj / "package.json"
    index_html = proj / "index.html"

    if pkg.is_file():
        try:
            blob = json.loads(pkg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            blob = {}
        scripts = blob.get("scripts") if isinstance(blob, dict) else None
        if isinstance(scripts, dict) and str(scripts.get("start") or "").strip():
            npm = shutil.which("npm") or "npm"
            try:
                subprocess.Popen(
                    [npm, "start"],
                    cwd=str(proj),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                lines.append("🔄 Started **npm start** in the background.")
                lines.append("")
                lines.append(
                    "🌐 Typical URL: **http://localhost:3000** (check the process output if the port differs)."
                )
            except (OSError, FileNotFoundError) as exc:
                lines.append(f"❌ Could not run `npm start`: `{exc}`")
        else:
            lines.append(
                "ℹ️ Found `package.json` but no **start** script — edit the project or run commands manually."
            )
    elif backend.is_file():
        node = shutil.which("node")
        if not node:
            lines.append("❌ **node** is not on `PATH`; install Node.js to run the backend.")
        else:
            try:
                subprocess.Popen(
                    [node, "server.js"],
                    cwd=str(backend.parent),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
                lines.append("🔄 Started **node server.js** (todo API).")
                lines.append("")
                lines.append(
                    f"🌐 Default API base: **http://127.0.0.1:{_TODO_BACKEND_DEFAULT_PORT}** "
                    "(matches the scaffolded backend; static UI is still localStorage until wired)."
                )
            except (OSError, FileNotFoundError) as exc:
                lines.append(f"❌ Could not start backend: `{exc}`")

    if index_html.is_file():
        try:
            import webbrowser

            webbrowser.open(index_html.resolve().as_uri())
            lines.append("")
            lines.append(f"🌐 Opened **{index_html.name}** in your default browser (file URL).")
        except (OSError, RuntimeError, TypeError):
            lines.append("")
            lines.append(f"📂 Open manually: `{index_html.resolve()}`")

    lines.append("")
    lines.append(
        "✅ **Done.** Leave background servers running while you use the app; stop them from a terminal when finished."
    )

    return {
        "mode": "chat",
        "text": "\n".join(lines).strip(),
        "intent": "start_app_success",
        "host_executor": True,
        "app_path": str(proj),
    }


__all__ = ["try_start_built_app_gateway_turn"]

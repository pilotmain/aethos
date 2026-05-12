"""Gateway NL: ``Development …`` / ``Dev …`` — best-effort workspace patches (todo scaffold)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.batch_executor import create_batch_files
from app.services.gateway.context import GatewayContext
from app.services.gateway.early_nl_host_actions import _workspace_root_for_nl
from app.services.host_executor_intent import parse_development_task_intent
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


def _sandbox_plan_can_take_handoff(settings: Any) -> bool:
    """True when owner-facing sandbox LLM plans are enabled.

    Uses strict ``bool`` checks so unit tests that use bare ``MagicMock`` settings do not
    accidentally treat unspecified flags as enabled.
    """
    en = getattr(settings, "nexa_sandbox_execution_enabled", False)
    llm = getattr(settings, "use_real_llm", False)
    if not isinstance(en, bool) or not isinstance(llm, bool):
        return False
    return bool(en) and bool(llm)


def _latest_todo_project(workspace: Path) -> Path | None:
    """Pick a todo-ish folder under the NL workspace (prefers ``*todo*`` in the name)."""
    if not workspace.is_dir():
        return None
    scored: list[tuple[int, int, Path]] = []
    for p in workspace.iterdir():
        if not p.is_dir():
            continue
        if not (p / "index.html").is_file() or not (p / "app.js").is_file():
            continue
        mtime = int(p.stat().st_mtime_ns)
        if "todo" in p.name.lower():
            scored.append((2, mtime, p))
        else:
            scored.append((1, mtime, p))
    if not scored:
        return None
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return scored[0][2]


def _patch_index_datetime_local(html: str) -> tuple[str, bool]:
    if "todoTime" in html or "datetime-local" in html.lower():
        return html, False
    m = re.search(r'(<input[^>]*\bid="task"[^>]*/>)', html, re.IGNORECASE)
    if not m:
        return html, False
    insert = (
        m.group(1)
        + "\n      <input id=\"todoTime\" type=\"datetime-local\" title=\"Due (optional)\" />"
    )
    return html.replace(m.group(1), insert, 1), True


def _patch_css_delete_button(css: str) -> tuple[str, bool]:
    if ".delete-btn" in css:
        return css, False
    add = (
        "\n.delete-btn { background: #ef4444; color: #f8fafc; border: none; "
        "padding: 0.25rem 0.5rem; border-radius: 4px; cursor: pointer; margin-left: 0.35rem; }\n"
    )
    return css + add, True


def _patch_appjs_add_delete(js: str) -> tuple[str, bool]:
    if "delete-btn" in js or "AETHOS_DEVNL_PATCH_DELETE" in js:
        return js, False
    anchor = "li.appendChild(completeBtn);"
    if anchor not in js or "originalIndex" not in js:
        return js, False
    block = """
    const del = document.createElement("button");
    del.type = "button";
    del.textContent = "Delete";
    del.className = "delete-btn";
    del.onclick = () => {
      items.splice(originalIndex, 1);
      save();
      render();
    };
    // AETHOS_DEVNL_PATCH_DELETE
"""
    return js.replace(anchor, anchor + block, 1), True


def _patch_appjs_time_wiring(js: str) -> tuple[str, bool]:
    if "getElementById(\"todoTime\")" in js or "getElementById('todoTime')" in js:
        return js, False
    needle = 'const input = document.getElementById("task");'
    if needle not in js:
        return js, False
    js2 = js.replace(
        needle,
        needle + '\nconst timeInput = document.getElementById("todoTime");',
        1,
    )
    changed = js2 != js
    if "items.push(v);" in js2:
        js2 = js2.replace(
            "items.push(v);",
            "items.push({ text: v, dueTime: (timeInput && timeInput.value) || \"\", "
            "completed: false, createdAt: new Date().toISOString() });",
            1,
        )
        changed = True
    if "input.value = \"\";" in js2 and "timeInput" in js2 and "timeInput.value = \"\"" not in js2:
        js2 = js2.replace('input.value = "";', 'input.value = "";\n    if (timeInput) timeInput.value = "";', 1)
        changed = True
    return js2, changed


def try_development_nl_gateway_turn(
    gctx: GatewayContext,
    raw_message: str,
    db: Session,
) -> dict[str, Any] | None:
    raw = (raw_message or "").strip()
    uid = (gctx.user_id or "").strip()
    if not raw or not uid:
        return None
    parsed = parse_development_task_intent(raw)
    if not parsed:
        return None
    task = str(parsed.get("task") or "").strip()[:4_000]
    if not task:
        return None

    settings = get_settings()
    if not bool(getattr(settings, "nexa_auto_approve_owner", True)):
        return None
    if not is_privileged_owner_for_web_mutations(db, uid):
        return None

    root = Path(_workspace_root_for_nl()).expanduser().resolve()
    proj = _latest_todo_project(root)
    if proj is None:
        return {
            "mode": "chat",
            "text": (
                "**No todo app found** in your workspace.\n\n"
                "Build one first, for example: **build a todo app** or "
                "**build a todo app with a database backend**."
            ),
            "intent": "development_nl_error",
            "host_executor": True,
        }

    tlow = task.lower()
    want_delete = "delete" in tlow and ("button" in tlow or "btn" in tlow or "remove" in tlow)
    want_time = "time" in tlow and (
        "picker" in tlow or "select" in tlow or "due" in tlow or "datetime" in tlow
    )

    rel_dir = proj.relative_to(root).as_posix()
    files_out: list[dict[str, Any]] = []
    notes: list[str] = []

    app_js_orig = (proj / "app.js").read_text(encoding="utf-8", errors="replace")
    app_js = app_js_orig
    css_orig = (proj / "styles.css").read_text(encoding="utf-8", errors="replace")
    css_txt = css_orig
    html_orig = (proj / "index.html").read_text(encoding="utf-8", errors="replace")
    html_txt = html_orig

    if want_delete:
        app_js, ch_js = _patch_appjs_add_delete(app_js)
        css_txt, ch_css = _patch_css_delete_button(css_txt)
        if ch_js:
            notes.append("Added a **Delete** control in `app.js`.")
        else:
            notes.append("`app.js` already had a delete-style control — skipped.")
        if ch_css:
            notes.append("Ensured **`.delete-btn`** styles in `styles.css`.")
        elif ch_js:
            notes.append("`styles.css` already defined `.delete-btn` — skipped.")

    if want_time:
        html_txt, ch_html = _patch_index_datetime_local(html_txt)
        if ch_html:
            notes.append("Inserted **`datetime-local`** in `index.html`.")
        else:
            notes.append("`index.html` already had a due-time field — skipped.")
        app_js, ch_js2 = _patch_appjs_time_wiring(app_js)
        if ch_js2:
            notes.append("Wired **`todoTime`** into `app.js` (basic save path).")

    if app_js != app_js_orig:
        files_out.append({"filename": f"{rel_dir}/app.js", "content": app_js})
    if css_txt != css_orig:
        files_out.append({"filename": f"{rel_dir}/styles.css", "content": css_txt})
    if html_txt != html_orig:
        files_out.append({"filename": f"{rel_dir}/index.html", "content": html_txt})

    if not files_out:
        # Let the sandbox planner handle broader "Development …" edits (change/update/…); it runs
        # after this turn in the gateway when we return None.
        if _sandbox_plan_can_take_handoff(settings):
            from app.services.gateway.sandbox_nl import _EXEC_WORD as _sandbox_plan_exec_hint

            if _sandbox_plan_exec_hint.search(raw):
                return None
        return {
            "mode": "chat",
            "text": (
                f"**Development task**\n\n_{task}_\n\n"
                f"**Project:** `{proj.name}`\n\n"
                "I can auto-apply **delete button** or **due time field** phrasing when you say that clearly. "
                "For larger edits, create a developer sub-agent and use `@agent_name …`.\n\n"
                "• **create a developer agent**\n"
                "• `/subagent list`"
            ),
            "intent": "development_nl_handoff",
            "host_executor": True,
        }

    res = create_batch_files(files_out, str(root), uid)
    ok = bool(res.get("success"))
    body_lines = [
        "**Development — workspace updated**" if ok else "**Development — write failed**",
        "",
        f"**Task:** _{task}_",
        f"**Project:** `{proj.name}`",
        "",
    ]
    body_lines += notes
    body_lines.append("")
    if ok:
        body_lines.append("_Refresh `index.html` in the browser to load changes._")
    else:
        body_lines.append(str(res.get("error") or "Unknown error from batch writer."))
    return {
        "mode": "chat",
        "text": "\n".join(body_lines).strip(),
        "intent": "development_nl_done" if ok else "development_nl_error",
        "host_executor": True,
    }


__all__ = ["try_development_nl_gateway_turn"]

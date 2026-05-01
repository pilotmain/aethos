"""One-shot health and release-readiness text for /dev doctor and /dev git."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agent_job_service import AgentJobService
from app.services.env_validator import collect_env_validation_issues, format_env_validation_report
from app.services.handoff_paths import PROJECT_ROOT
from app.services.job_diagnostics import (
    collect_job_diagnostics,
    durable_preferences_count,
    format_last_memory_line,
)
from app.services.memory_preferences import get_memory_preferences_dict
from app.services.system_memory_files import memory_path, soul_path
from app.services.worker_heartbeat import HEARTBEAT_PATH, RUNTIME_DIR, aider_on_path, read_heartbeat

logger = logging.getLogger(__name__)

_HOST_PID = RUNTIME_DIR / "host_dev_executor.pid"
_HOST_LOG = RUNTIME_DIR / "host_dev_executor.log"
_PY = Path(sys.executable or "python3").resolve()


def _get_branch(project_root: str) -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=4,
        )
        return (r.stdout or "").strip() if r.returncode == 0 else "unknown"
    except (OSError, subprocess.SubprocessError) as e:  # missing git, timeout, etc.
        logger.info("nexa doctor _get_branch: %s", e)
        return f"unavailable ({type(e).__name__})"


def _is_agent_branch(branch: str) -> bool:
    b = (branch or "").strip()
    return b.startswith("agent/job-")


def _git_porcelain_counts(project_root: str) -> tuple[int, int]:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=6,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.info("nexa doctor _git_porcelain_counts: %s", e)
        return -1, -1
    if r.returncode != 0:
        return -1, -1
    lines = [x for x in (r.stdout or "").splitlines() if x.strip()]
    tracked, untr = 0, 0
    for line in lines:
        if line.startswith("?? "):
            untr += 1
        else:
            tracked += 1
    return tracked, untr


def _soul_uncommitted_note(project_root: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain", "--", "soul.md"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=4,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.info("nexa doctor _soul_uncommitted_note: %s", e)
        return f"soul.md git check skipped ({type(e).__name__})"
    st = (r.stdout or "").strip() if r.returncode == 0 else ""
    if not st:
        return None
    if st.startswith(" M") or st.startswith("M "):
        return "soul.md is modified and uncommitted (keeps identity local)."
    if st.startswith("??"):
        return "soul.md is untracked (local only)."
    return "soul.md has local changes not in the last commit."


def _public_web_access_section() -> str:
    s = get_settings()
    on = bool(s.nexa_web_access_enabled)
    bprev = bool(s.nexa_browser_preview_enabled)
    return "\n".join(
        [
            "**Public web access**",
            f"- enabled: **{'yes' if on else 'no'}**",
            "- mode: read-only (HTTP(s) + HTML text extract; not a full browser)",
            "- internal / private hostnames: **owner-only** (SSRF policy for non-owners)",
            "**Browser preview (optional, owner, public URLs)**",
            f"- enabled: **{'yes' if bprev else 'no'}** (set `NEXA_BROWSER_PREVIEW_ENABLED` + `pip install playwright` + `playwright install chromium` on the host)",
        ]
    )


def _documents_section(db: Session, settings) -> str:
    from app.services.document_generation import count_all_document_artifacts

    try:
        n = int(count_all_document_artifacts(db))
    except (TypeError, ValueError) as e:
        logger.info("doctor documents count: %s", e)
        n = -1
    days = int(getattr(settings, "nexa_document_retention_days", None) or 30)
    nshow = f"**{n}**" if n >= 0 else "**unavailable** (check DB)"
    rel = ".runtime/generated_documents"
    return "\n".join(
        [
            "**Documents** (chat & template exports; per-user files)",
            "- enabled: **yes**",
            f"- storage: `{rel}` (under project root, same as `RUNTIME_DIR` layout)",
            f"- generated count (all rows in DB): {nshow}",
            f"- retention: **{days} days**  (`NEXA_DOCUMENT_RETENTION_DAYS` — no scheduled cleanup job yet)",
            "- **docx** / **pdf**: via `python-docx` and ReportLab (see `requirements.txt`)",
        ]
    )


def _web_search_section() -> str:
    s = get_settings()
    en = bool(s.nexa_web_search_enabled)
    p = (s.nexa_web_search_provider or "none").lower().strip() or "none"
    key = (s.nexa_web_search_api_key or "").strip()
    kyes = "yes" if key else "no"
    m = int(s.nexa_web_search_max_results or 5)
    return "\n".join(
        [
            "**Web search** (read-only: titles, snippets, URLs; no result-page automation)",
            f"- enabled: **{'yes' if en else 'no'}**  (`NEXA_WEB_SEARCH_ENABLED`)",
            f"- provider: **{p}**  (brave, tavily, serpapi, none)",
            f"- key configured: **{kyes}**  (key value is never shown)",
            f"- max results: **{m}**  (`NEXA_WEB_SEARCH_MAX_RESULTS`)",
        ]
    )


def _api_health() -> str:
    s = get_settings()
    url = f"{s.api_base_url.rstrip('/')}{s.api_v1_prefix.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=2) as r:  # nosec: local dev URL
            if r.status == 200:
                return "ok (HTTP 200)"
            return f"http {r.status}"
    except urllib.error.URLError as e:
        return f"unreachable ({e!s})"[:200]
    except (TimeoutError, OSError) as e:
        return f"unreachable ({type(e).__name__})"


def _db_status(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:  # noqa: BLE001
        logger.info("doctor db: %s", e)
        return f"error ({type(e).__name__})"


def _bot_process_status() -> str:
    try:
        r = subprocess.run(
            ["pgrep", "-f", "app.bot.telegram_bot"],
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError) as e:
        logger.info("nexa doctor _bot_process_status: %s", e)
        return f"pgrep unavailable on this system ({type(e).__name__})"
    n = len([x for x in (r.stdout or "").splitlines() if x.strip()]) if r.returncode == 0 else 0
    if n:
        return f"likely on host (pgrep: {n})"
    return "no `app.bot.telegram_bot` process seen on this host (or runs only in a container)."


def _host_executor_status() -> tuple[str, str]:
    if not _HOST_PID.is_file():
        return "no pid file", f"log: {'yes' if _HOST_LOG.is_file() else 'no'}"
    try:
        raw = (_HOST_PID.read_text(encoding="utf-8") or "").strip()
    except OSError as e:
        return f"read error: {e}", f"log: {'yes' if _HOST_LOG.is_file() else 'no'}"
    m = re.search(r"(\d+)", raw)
    if not m:
        return f"unparsed pid file: {raw[:30]!r}…", f"log: {'yes' if _HOST_LOG.is_file() else 'no'}"
    pid = int(m.group(1))
    try:
        os.kill(pid, 0)
        return f"likely running (pid {pid})", f"log: {'yes' if _HOST_LOG.is_file() else 'no'}"
    except OSError:
        return f"stale/missing (pid {pid} not alive)", f"log: {'yes' if _HOST_LOG.is_file() else 'no'}"


def _env_cmd(name: str) -> str:
    v = (os.environ.get(name) or "").strip()
    return "set" if v else "unset"


def _pending_approvalish(db: Session, user_id: str) -> str:
    js = AgentJobService()
    rows = js.list_jobs(db, user_id, limit=200)
    dev = [j for j in rows if (j.worker_type or "") == "dev_executor"]
    need = 0
    for j in dev:
        st = j.status or ""
        if st in {
            "needs_approval",
            "needs_risk_approval",
            "waiting_approval",
            "needs_commit_approval",
            "changes_requested",
            "approved_to_commit",
        }:
            need += 1
    n_apq = len([j for j in dev if (j.status or "") == "approved"])
    if need or n_apq:
        return f"needs you: {need}  ·  `approved` (queue): {n_apq}"
    return "no blocking items in the recent 200 job rows (still check /dev queue for detail)."


def _aider_str() -> str:
    if aider_on_path():
        return "on PATH"
    return "not on PATH (install or use DEV_AGENT_COMMAND only)"


def _creator_in_soul(raw: str) -> bool:
    t = (raw or "").lower()
    return "creator" in t and "nexa" in t


def _soul_read_status() -> tuple[str, str]:
    p = soul_path()
    if not p.is_file():
        return "missing", "— (optional; Nexa still runs without soul.md on disk)"
    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
        c = _creator_in_soul(raw)
        return (f"found, creator: {'configured' if c else 'unclear/optional'}", "read")
    except OSError:
        return "unreadable", "read error"


def format_git_brief() -> str:
    """/dev git — short, no tokens."""
    pr = str(PROJECT_ROOT)
    br = _get_branch(pr)
    dirty, untr = _git_porcelain_counts(pr)
    st = "git missing or error"
    if shutilwhich("git"):
        r0 = subprocess.run(
            ["git", "-C", pr, "status", "-sb"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        st = ((r0.stdout or "").splitlines() or [""])[0] if r0.returncode == 0 else (r0.stderr or "err")[:300]
    rc2 = subprocess.run(
        ["git", "-C", pr, "log", "-1", "--oneline"],
        capture_output=True,
        text=True,
        timeout=4,
    )
    lastc = (rc2.stdout or "").splitlines()[0] if rc2.returncode == 0 else "—"
    rr = subprocess.run(
        ["git", "-C", pr, "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        timeout=3,
    )
    rurl = (rr.stdout or "").splitlines()[0] if rr.returncode == 0 and (rr.stdout or "") else "— (no origin)"
    solw = _soul_uncommitted_note(pr)
    lines: list[str] = [
        "**Nexa git (brief)**",
        f"- branch: `{br}`",
        f"- status: `{st!s}`"[:2000],
        f"- last commit: `{lastc!s}`"[:2000],
        f"- changed/untracked: tracked-ish lines {dirty}  ·  untracked {untr}",
        f"- `origin` URL: `{rurl[:300]!s}`",
    ]
    if _is_agent_branch(br):
        lines.append(
            "- you are on an `agent/…` branch: open a PR, merge to main when you are ready, then restart the stack on that commit"
        )
    if solw:
        lines.append(f"- warning: {solw}")
    if br != "main" and (br or "").lower() not in ("master", "unknown"):
        lines.append("- you are not on `main` — that is expected for a feature, but not for a production run.")
    return "\n".join(lines)[:5000]


def shutilwhich(x: str) -> str | None:
    import shutil

    return shutil.which(x)


def build_nexa_doctor_text(
    db: Session, app_user_id: str, *, telegram_user_id: int | None = None
) -> str:
    s = get_settings()
    pr = str(PROJECT_ROOT)
    br = _get_branch(pr)
    mp = memory_path()
    mp_ex = mp.is_file()
    soul_t, _ = _soul_read_status()
    soul_git = _soul_uncommitted_note(pr) or "tracked/committed in git, or not under git in this worktree"
    lastm = format_last_memory_line() if mp_ex else "—"
    get_memory_preferences_dict()  # warm cache; durable count uses file snapshot
    dct = durable_preferences_count()

    from app.services.llm_key_resolution import doctor_user_llm_block
    from app.services.user_capabilities import access_section_for_doctor, is_owner_ids_configured

    acc_block = ""
    if telegram_user_id is not None:
        acc_block = access_section_for_doctor(telegram_user_id, db).strip()
        if not is_owner_ids_configured():
            acc_block += "\n• Warning: set `TELEGRAM_OWNER_IDS` in production so the first /start is not the only “owner”."
    ullm = doctor_user_llm_block(db, telegram_user_id=telegram_user_id)
    lines: list[str] = [
        "**Nexa Doctor**",
    ]
    if acc_block:
        lines += ["", acc_block, ""]
    else:
        lines.append("")
    if ullm:
        lines += [ullm, ""]
    lines += [
        "**Runtime**",
        f"- API: **{_api_health()}**  (`{s.api_base_url}` + health)",
        f"- DB: **{_db_status(db)}**",
        f"- bot process: {_bot_process_status()}",
        f"- worker heartbeat: `{HEARTBEAT_PATH}`  status: {(read_heartbeat() or {}).get('status') or '—'}",
    ]
    if s.dev_executor_on_host or (os.environ.get("DEV_EXECUTOR_ON_HOST") or "").strip() in (
        "1",
        "true",
        "yes",
    ):
        hst, hlg = _host_executor_status()
        lines.append(
            f"- host executor: **{hst}**  `DEV_EXECUTOR_ON_HOST=1`  ·  {hlg}"
        )

    de_py = (os.environ.get("DEV_EXECUTOR_PYTHON") or "").strip()
    venv = (PROJECT_ROOT / ".venv" / "bin" / "python3")
    venv2 = (PROJECT_ROOT / ".venv" / "bin" / "python")
    venv_line = f"{venv!s} exists" if venv.is_file() else f"{venv2!s} exists" if venv2.is_file() else "no `.venv/bin/python` in project (create venv in repo root if you run workers here)"

    lines += [
        "",
        "**Dev agent (host context)**",
        f"- aider: **{_aider_str()}**",
        f"- `DEV_AGENT_COMMAND`: {_env_cmd('DEV_AGENT_COMMAND')}",
        f"- `DEV_EXECUTOR_PYTHON`: {de_py or 'unset'}" + (
            f"  (exists: yes)" if de_py and Path(de_py).is_file() else "  (path missing?)" if de_py else ""
        ),
        f"- this Python: `{_PY!s}`",
        f"- project `.venv`: {venv_line}",
        f"- jobs (recent, summary): {_pending_approvalish(db, app_user_id)}",
    ]
    if _is_agent_branch(br):
        lines += [
            "",
            "**Branch (merge safety)**",
            f"- you are on **`{br!s}`**  —  next: run tests, open a PR, merge to main, restart API and bot. Nexa will not auto-merge this branch.",
        ]

    lines += [
        "",
        _public_web_access_section(),
    ]
    lines += ["", _web_search_section()]
    lines += ["", _documents_section(db, s)]

    lines += [
        "",
        "**Memory**",
        f"- `soul.md`: {soul_t}  ·  git: {soul_git!s}"[:2000],
        f"- `memory.md`: {'**found**' if mp_ex else '**missing**'}" + f"  ·  last line (trimmed): `{lastm[:200]!s}`",
        f"- durable preferences detected (heuristic, max few): {dct}",
    ]

    lines += ["", "**Env validation**", format_env_validation_report()]

    rows = AgentJobService().list_jobs(db, app_user_id, limit=100)
    jw = collect_job_diagnostics(db, list(rows))
    if jw:
        lines += ["", "**Job / queue heuristics**", *[f"• {w}" for w in jw[:20]]]
    wlist = collect_env_validation_issues()
    snote = _soul_uncommitted_note(pr)
    wlines: list[str] = list(jw[:5])
    if snote and snote not in wlines:
        wlines.append(snote)
    if wlist and not any("Both DEV_EXECUTOR" in w for w in wlines):
        wlines.append(wlist[0][:500])
    if wlines:
        lines += ["", "**Warnings (top)**", *[f"• {x}" for x in wlines[:12]]]

    lines += [
        "",
        "**Next actions (optional)**",
        f"- If something looks off: re-run this report after you fix the host, DB, and `.env`.",
    ]
    if snote and "soul" in snote:
        lines.append("- Commit or stash `soul.md` only if you want it in git; it is often kept local for identity text.")
    if _is_agent_branch(br):
        lines.append(
            f"- For branch **{br}** — finish work, then merge to **main** and restart services so the bot runs the new code."
        )
    if not venv.is_file() and not venv2.is_file():
        lines.append("- Add `.venv` under the project root to match the scripts in this repository.")
    return "\n".join(lines)[:12_000]


# --- for tests: section markers are plain text in build_nexa_doctor_text (Runtime / Memory / etc.)

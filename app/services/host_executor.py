"""
Approval-gated host execution for local_tool jobs.

No arbitrary shell: only fixed tool names and argv lists. Execution happens only after
the user approves the job and local_tool_worker runs it — never directly from LLM output.

``git`` subprocesses optionally use :mod:`app.services.operator_shell_cli` (same ``$SHELL`` login
session + nvm/rc loader as operator ``vercel`` / ``gh``) when ``NEXA_OPERATOR_CLI_PROFILE_SHELL`` is enabled.

When ``db`` and ``job`` with ``user_id`` are provided, permission registry + grants are enforced.
"""
from __future__ import annotations

import logging
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.services.host_executor_chain import (
    chain_step_output_failed,
    merge_chain_step,
    parse_chain_inner_allowed,
)
from app.services.host_executor_intent import safe_relative_path
from app.services.operator_cli_absolute import apply_operator_cli_absolute_fallback
from app.services.operator_cli_path import cli_environ_for_operator
from app.services.operator_shell_cli import profile_shell_enabled, run_allowlisted_argv_via_login_shell

logger = logging.getLogger(__name__)

# Keys -> full argv (no user-controlled tokens in argv).
ALLOWED_RUN_COMMANDS: dict[str, list[str]] = {
    "pytest": ["python", "-m", "pytest"],
    "git_status_short": ["git", "status", "--short", "--branch"],
}

# Optional git_push remote/ref — argv only (no shell).
_PUSH_REMOTE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,63}$")
_PUSH_REF_RE = re.compile(r"^[a-zA-Z0-9/_.-]{1,200}$")
# Vercel project name (slug) — no path separators.
_VERCEL_PROJECT_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}$")

_PATH_BLOCKED_SUBSTRINGS = (
    ".env",
    ".ssh",
    "credentials",
    "secrets",
    ".pem",
    "id_rsa",
    "known_hosts",
)

# On-demand multi-file reads (text-ish only; no shell; no indexing).
TEXT_INTEL_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".html",
        ".htm",
        ".css",
        ".yaml",
        ".yml",
        ".toml",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".swift",
        ".kt",
        ".vue",
        ".xml",
        ".csv",
        ".svg",
        ".sql",
        ".sh",
        ".bash",
        ".zsh",
    }
)


def _host_settings():
    return get_settings()


def _base_work_dir() -> Path:
    s = _host_settings()
    raw = (getattr(s, "host_executor_work_root", None) or str(REPO_ROOT)).strip()
    return Path(raw).expanduser().resolve()


def _resolve_exec_root(payload: dict[str, Any], base: Path) -> Path:
    """Optional subdirectory (relative to host work root) for git/commands cwd."""
    cr = str(payload.get("cwd_relative") or "").strip()
    if not cr:
        return base
    sr = safe_relative_path(cr.replace("\\", "/"))
    if not sr:
        raise ValueError("invalid cwd_relative")
    return _safe_join_under_root(base, sr)


def _safe_join_under_root(root: Path, relative: str) -> Path:
    rel = (relative or "").strip().replace("\\", "/").lstrip("/")
    if ".." in Path(rel).parts or rel.startswith("/"):
        raise ValueError("path must be relative and cannot contain '..'")
    out = (root / rel).resolve()
    try:
        out.relative_to(root)
    except ValueError as e:
        raise ValueError("path escapes work root") from e
    return out


def argv_for_vercel_remove(payload: dict[str, Any]) -> list[str]:
    """Build fixed argv for ``vercel remove <project> --yes`` (non-interactive only)."""
    name = (payload.get("vercel_project_name") or payload.get("project_name") or "").strip()
    if not name or not _VERCEL_PROJECT_RE.fullmatch(name):
        raise ValueError(
            "vercel_project_name or project_name is required and must be a single Vercel project slug "
            "(alphanumeric, dot, underscore, hyphen; no path characters)"
        )
    if payload.get("vercel_yes") is not True:
        raise ValueError(
            "vercel_yes must be JSON true to confirm non-interactive removal (runs vercel remove … --yes)"
        )
    return ["vercel", "remove", name, "--yes"]


def argv_for_git_push(payload: dict[str, Any]) -> list[str]:
    """Build fixed argv for ``git push`` (optional remote + ref)."""
    remote = (payload.get("push_remote") or "").strip()
    ref = (payload.get("push_ref") or "").strip()
    if remote and not _PUSH_REMOTE_RE.fullmatch(remote):
        raise ValueError("push_remote must match [a-zA-Z][a-zA-Z0-9_.-]{0,63}")
    if ref and not _PUSH_REF_RE.fullmatch(ref):
        raise ValueError("push_ref must be a branch/ref name (allowed charset only)")
    if ref and not remote:
        raise ValueError("push_ref requires push_remote")
    if remote and ref:
        return ["git", "push", remote, ref]
    if remote:
        return ["git", "push", remote]
    return ["git", "push"]


def _path_allowed_for_io(p: Path) -> None:
    sp = str(p).lower()
    for b in _PATH_BLOCKED_SUBSTRINGS:
        if b in sp:
            raise ValueError(f"path not allowed (blocked segment): {b}")


def _run_argv(
    argv: list[str],
    *,
    cwd: Path,
    timeout: int,
) -> tuple[int, str, str]:
    argv = apply_operator_cli_absolute_fallback(list(argv))
    if profile_shell_enabled() and argv and Path(argv[0]).name == "git":
        out = run_allowlisted_argv_via_login_shell(
            argv,
            cwd=str(cwd),
            timeout=float(timeout),
            env=cli_environ_for_operator(),
        )
        if out.get("error") == "timeout":
            logger.warning("host_executor profile_shell timeout argv0=%s", argv[:1])
            return -1, "", "timeout"
        if out.get("error"):
            logger.warning(
                "host_executor profile_shell argv0=%s err=%s",
                argv[:1],
                str(out.get("error"))[:200],
            )
            return (
                -1,
                (out.get("stdout") or "")[:24_000],
                (out.get("stderr") or "")[:24_000],
            )
        code = int(out.get("exit_code") if out.get("exit_code") is not None else (0 if out.get("ok") else 1))
        so = (out.get("stdout") or "")[:24_000]
        se = (out.get("stderr") or "")[:24_000]
        logger.info(
            "host_executor profile_shell argv0=%s exit=%s ok=%s",
            argv[0] if argv else "",
            code,
            code == 0,
        )
        return code, so, se
    try:
        r = subprocess.run(  # noqa: S603 — argv constructed only from allowlists
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=cli_environ_for_operator(),
        )
    except subprocess.TimeoutExpired:
        logger.warning("host_executor timeout argv0=%s", argv[:1])
        return -1, "", "timeout"
    except (OSError, FileNotFoundError) as e:
        logger.warning("host_executor spawn failed argv0=%s err=%s", argv[:1], type(e).__name__)
        return -1, "", str(e)[:2000]
    out = (r.stdout or "")[:24_000]
    err = (r.stderr or "")[:24_000]
    logger.info(
        "host_executor argv0=%s exit=%s ok=%s",
        argv[0] if argv else "",
        r.returncode,
        r.returncode == 0,
    )
    return r.returncode, out, err


def execute_payload(
    payload: dict[str, Any],
    *,
    db: Any | None = None,
    job: Any | None = None,
) -> str:
    """
    Run one host action from an allowlisted payload (used by tests and worker).

    Permission + workspace checks run when enforcement is on, ``db`` and ``job.user_id`` are set
    (production worker with ``NEXA_ACCESS_PERMISSIONS_ENFORCED=1``).
    Unit tests call with payload only → checks skipped.

    Returns user-facing text (stdout/stderr summary). Raises ValueError on validation.
    """
    s = _host_settings()
    if not getattr(s, "nexa_host_executor_enabled", False):
        raise ValueError(
            "Host executor is disabled. Set NEXA_HOST_EXECUTOR_ENABLED=1 on the worker host."
        )

    from app.services.enforcement_pipeline import (
        audit_enforcement_path_if_enabled,
        enforce_host_execution_policy,
    )

    payload = enforce_host_execution_policy(payload, boundary="host_executor")

    action = (payload.get("host_action") or payload.get("action") or "").strip().lower()
    uid = getattr(job, "user_id", None) if job is not None else None
    enforce_perm = bool(getattr(s, "nexa_access_permissions_enforced", False))
    if db is not None and uid and enforce_perm:
        from app.services.trust_audit_correlation import warn_missing_correlation

        warn_missing_correlation(
            payload,
            boundary="host_executor",
            logger=logger,
            hint=f"host_action={action}",
        )

    if db is not None and uid:
        audit_enforcement_path_if_enabled(
            db,
            boundary="host_executor",
            action_type=action or "unknown",
            user_id=str(uid),
            extra={"sensitivity": payload.get("_nexa_sensitivity")},
        )
    timeout = min(
        max(int(getattr(s, "host_executor_timeout_seconds", 120)), 5),
        3600,
    )
    root = _base_work_dir()
    exec_root = _resolve_exec_root(payload, root)
    max_bytes = min(max(int(getattr(s, "host_executor_max_file_bytes", 262_144)), 1024), 2_000_000)

    chain_inner = bool(payload.get("_nexa_chain_inner_step"))
    enforce = enforce_perm
    grants: list[Any] = []
    check_perms = bool(db is not None and uid and enforce and not chain_inner)
    if check_perms:
        from app.services.access_permissions import (
            check_host_executor_chain_job,
            check_host_executor_job,
        )

        if action == "chain":
            ok, err, grants = check_host_executor_chain_job(
                db,
                owner_user_id=str(uid),
                work_root=root,
                payload=payload,
            )
        else:
            ok, err, grants = check_host_executor_job(
                db,
                owner_user_id=str(uid),
                host_action=action,
                work_root=root,
                payload=payload,
            )
        if not ok:
            raise ValueError(err)

    def _finalize_output(text: str) -> str:
        if db is None or not uid or not enforce or not grants:
            return text
        from app.services.access_permissions import finalize_permission_use

        prefix = finalize_permission_use(
            db, str(uid), grants, host_action=action, payload=payload
        )
        return f"{prefix}\n\n{text}" if prefix else text

    if action == "chain":
        if not bool(getattr(s, "nexa_host_executor_chain_enabled", False)):
            raise ValueError(
                "Chain host actions are disabled. Set NEXA_HOST_EXECUTOR_CHAIN_ENABLED=1 on the worker."
            )
        allowed_inner = parse_chain_inner_allowed(s)
        actions_in = payload.get("actions")
        if not isinstance(actions_in, list) or not actions_in:
            raise ValueError("chain requires a non-empty actions list")
        max_s = min(max(int(getattr(s, "nexa_host_executor_chain_max_steps", 10)), 1), 20)
        if len(actions_in) > max_s:
            raise ValueError(f"chain has {len(actions_in)} steps; max is {max_s}")
        for i, step in enumerate(actions_in):
            if not isinstance(step, dict):
                raise ValueError(f"chain step {i + 1} must be an object")
            iha = (step.get("host_action") or "").strip().lower()
            if iha == "chain":
                raise ValueError("nested chain is not allowed")
            if iha not in allowed_inner:
                raise ValueError(
                    f"chain step {i + 1}: host_action {iha!r} is not allowed in a chain; "
                    f"allowed: {sorted(allowed_inner)}"
                )
        stop_on = payload.get("stop_on_failure", True)
        if not isinstance(stop_on, bool):
            stop_on = True
        parts_out: list[str] = []
        n_actions = len(actions_in)
        total_start = time.perf_counter()
        success_count = 0

        def _log_chain_summary(*, exit_reason: str) -> None:
            total_ms = (time.perf_counter() - total_start) * 1000.0
            logger.info(
                "Chain completed (%s): %s/%s steps successful in %.2fms (stop_on_failure=%s)",
                exit_reason,
                success_count,
                n_actions,
                total_ms,
                stop_on,
                extra={
                    "nexa_event": "chain_summary",
                    "chain_exit_reason": exit_reason,
                    "chain_total_steps": n_actions,
                    "chain_success_count": success_count,
                    "chain_total_duration_ms": round(total_ms, 2),
                    "chain_stop_on_failure": stop_on,
                },
            )

        for i, step in enumerate(actions_in):
            merged = merge_chain_step(payload, step)
            iha = (merged.get("host_action") or "").strip().lower()
            merged_inner = dict(merged)
            merged_inner["_nexa_chain_inner_step"] = True
            step_start = time.perf_counter()
            try:
                out = execute_payload(merged_inner, db=db, job=job)
            except ValueError as e:
                step_ms = (time.perf_counter() - step_start) * 1000.0
                logger.info(
                    "Chain step %s/%s (%s) validation error",
                    i + 1,
                    n_actions,
                    iha,
                    extra={
                        "nexa_event": "chain_step",
                        "chain_step": i + 1,
                        "chain_total_steps": n_actions,
                        "host_action": iha,
                        "duration_ms": round(step_ms, 2),
                        "success": False,
                        "error": str(e)[:2000],
                    },
                )
                parts_out.append(f"### Step {i + 1} ({iha}) — error\n\n{e}")
                if stop_on:
                    parts_out.append("_Stopped (stop_on_failure=True)._")
                    _log_chain_summary(exit_reason="stop_on_failure_validation")
                    return _finalize_output("\n\n".join(parts_out))
                continue
            step_ms = (time.perf_counter() - step_start) * 1000.0
            step_ok = not chain_step_output_failed(out)
            if step_ok:
                success_count += 1
            err_snippet = (out or "")[:500] if not step_ok else None
            logger.info(
                "Chain step %s/%s (%s) done",
                i + 1,
                n_actions,
                iha,
                extra={
                    "nexa_event": "chain_step",
                    "chain_step": i + 1,
                    "chain_total_steps": n_actions,
                    "host_action": iha,
                    "duration_ms": round(step_ms, 2),
                    "success": step_ok,
                    "error": err_snippet,
                },
            )
            parts_out.append(f"### Step {i + 1} ({iha})\n\n{out}")
            if stop_on and chain_step_output_failed(out):
                parts_out.append("_Stopped (stop_on_failure=True) after a failed step._")
                _log_chain_summary(exit_reason="stop_on_failure_step")
                return _finalize_output("\n\n".join(parts_out))
        _log_chain_summary(exit_reason="complete")
        return _finalize_output("\n\n".join(parts_out))

    if action == "plugin_skill":
        from app.services.skills.plugin_skill_bridge import run_plugin_skill_sync

        name = (payload.get("skill_name") or "").strip()
        if not name:
            raise ValueError("plugin_skill requires skill_name")
        inp = payload.get("input")
        if inp is not None and not isinstance(inp, dict):
            raise ValueError("plugin_skill input must be an object")
        raw = run_plugin_skill_sync(name, dict(inp or {}))
        return _finalize_output(str(raw)[:24_000])

    if action == "git_status":
        code, out, err = _run_argv(
            ["git", "status", "--short", "--branch"],
            cwd=exec_root,
            timeout=min(timeout, 60),
        )
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        if code != 0:
            return _finalize_output(f"(exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000] or "(empty)")

    if action == "run_command":
        name = (payload.get("run_name") or "").strip().lower()
        if name not in ALLOWED_RUN_COMMANDS:
            raise ValueError(
                f"unknown or disallowed run_name {name!r}; allowed: {sorted(ALLOWED_RUN_COMMANDS)}"
            )
        argv = list(ALLOWED_RUN_COMMANDS[name])
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=timeout)
        pieces = []
        if out.strip():
            pieces.append(out)
        if err.strip():
            pieces.append("STDERR:\n" + err)
        msg = "\n".join(pieces) if pieces else "(no output)"
        if code != 0:
            return _finalize_output(f"(exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000])

    if action == "file_read":
        rel = (payload.get("relative_path") or "").strip()
        if not rel:
            raise ValueError("file_read requires relative_path")
        path = _safe_join_under_root(root, rel)
        _path_allowed_for_io(path)
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if path.is_dir():
            raise ValueError(
                f"{path} is a folder, not a file. Use \"analyze folder {path}\" "
                "or list that path, or provide a specific file path."
            )
        if not path.is_file():
            raise ValueError(f"Not a readable file: {path}")
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise ValueError(f"file too large (max {max_bytes} bytes)")
        text = data.decode("utf-8", errors="replace")
        logger.info("host_executor file_read ok bytes=%s", len(data))
        return _finalize_output(text[:max_bytes])

    if action == "file_write":
        rel = (payload.get("relative_path") or "").strip()
        content = payload.get("content")
        if not rel or content is None:
            raise ValueError("file_write requires relative_path and content")
        path = _safe_join_under_root(root, rel)
        _path_allowed_for_io(path)
        if path.exists() and path.is_dir():
            raise ValueError("path is a directory")
        b = content if isinstance(content, bytes) else str(content).encode("utf-8")
        if len(b) > max_bytes:
            raise ValueError(f"content too large (max {max_bytes} bytes)")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b)
        logger.info("host_executor file_write ok path_suffix=%s", rel[-64:])
        return _finalize_output(f"Wrote {len(b)} bytes to {rel}")

    if action == "list_directory":
        raw_abs = payload.get("nexa_permission_abs_targets")
        if isinstance(raw_abs, list) and raw_abs:
            try:
                dirp = Path(str(raw_abs[0])).expanduser().resolve()
            except OSError as e:
                raise ValueError("invalid list_directory absolute target") from e
            _path_allowed_for_io(dirp)
        else:
            rel = (payload.get("relative_path") or ".").strip() or "."
            dirp = _safe_join_under_root(root, rel)
            _path_allowed_for_io(dirp)
        if not dirp.is_dir():
            raise ValueError("list_directory target must be a directory")
        lines: list[str] = []
        for i, ch in enumerate(sorted(dirp.iterdir(), key=lambda p: p.name.lower())):
            if i >= 200:
                lines.append("… (truncated at 200 entries)")
                break
            kind = "dir" if ch.is_dir() else "file"
            lines.append(f"{kind}\t{ch.name}")
        logger.info("host_executor list_directory entries=%s", min(len(lines), 200))
        return _finalize_output("\n".join(lines) if lines else "(empty)")

    if action == "find_files":
        rel = (payload.get("relative_path") or ".").strip() or "."
        pat = (payload.get("glob") or payload.get("pattern") or "*").strip()
        if len(pat) > 120 or "/" in pat or "\\" in pat:
            raise ValueError("glob pattern too large or contains path separators")
        if not re.match(r"^[A-Za-z0-9_.*?\-\[\]]+$", pat):
            raise ValueError("invalid glob pattern")
        base = _safe_join_under_root(root, rel)
        _path_allowed_for_io(base)
        if not base.is_dir():
            raise ValueError("find_files base must be a directory")
        found: list[str] = []
        ext_raw = payload.get("extensions")
        ext_filter: frozenset[str] | None = None
        if isinstance(ext_raw, list) and ext_raw:
            ext_filter = frozenset(
                (e if str(e).startswith(".") else f".{str(e).lower()}").lower()
                for e in ext_raw
                if str(e).strip()
            )
        for i, p in enumerate(sorted(base.glob(pat), key=lambda x: str(x).lower())):
            if ext_filter is not None and p.suffix.lower() not in ext_filter:
                continue
            if i >= 500:
                found.append("… (truncated at 500 matches)")
                break
            try:
                rp = p.resolve().relative_to(root)
                found.append(str(rp).replace("\\", "/"))
            except ValueError:
                continue
        logger.info("host_executor find_files matches=%s", min(len(found), 500))
        return _finalize_output("\n".join(found) if found else "(no matches)")

    if action == "read_multiple_files":
        logger.info(
            "READ_MULTIPLE_FILES base=%s abs_targets=%s",
            payload.get("base"),
            payload.get("nexa_permission_abs_targets"),
        )
        max_files = min(
            max(int(getattr(s, "host_executor_read_multiple_max_files", 20)), 1),
            50,
        )
        total_cap = min(max_bytes * max_files, 2_500_000)
        keyword = (payload.get("keyword") or "").strip().lower()

        ext_raw = payload.get("extensions")
        if isinstance(ext_raw, list) and ext_raw:
            ext_set = frozenset(
                (e if str(e).startswith(".") else f".{str(e)}").lower()
                for e in ext_raw
                if str(e).strip()
            )
        else:
            ext_set = TEXT_INTEL_EXTENSIONS

        explicit = payload.get("relative_paths")
        chunks_out: list[str] = []
        bytes_used = 0

        def add_file(rel_display: str, fp: Path) -> bool:
            nonlocal bytes_used
            _path_allowed_for_io(fp)
            if not fp.is_file():
                return True
            if fp.suffix.lower() not in ext_set:
                return True
            data = fp.read_bytes()
            if b"\x00" in data[:8000]:
                chunks_out.append(f"=== FILE: {rel_display} ===\n[skipped: binary]\n")
                return True
            text = data.decode("utf-8", errors="replace")
            if keyword and keyword not in text.lower():
                return True
            take = text[:max_bytes]
            piece = f"=== FILE: {rel_display} ===\n{take}"
            if bytes_used + len(piece.encode("utf-8", errors="replace")) > total_cap:
                chunks_out.append(
                    "[Bundle cap reached — remaining files omitted. Narrow the folder or extensions.]"
                )
                return False
            chunks_out.append(piece)
            bytes_used += len(piece.encode("utf-8", errors="replace"))
            return True

        if isinstance(explicit, list) and explicit:
            for rp in explicit[:max_files]:
                rs = str(rp).strip().replace("\\", "/").lstrip("/")
                if not rs:
                    continue
                fp = _safe_join_under_root(root, rs)
                if not add_file(rs, fp):
                    break
        else:
            raw_abs = payload.get("nexa_permission_abs_targets")
            has_abs = isinstance(raw_abs, list) and raw_abs and str(raw_abs[0]).strip()
            if has_abs:
                b_raw = payload.get("base")
                if not b_raw or not str(b_raw).strip():
                    raise ValueError(
                        "read_multiple_files missing base (required when nexa_permission_abs_targets is set)"
                    )
                try:
                    ref = Path(str(raw_abs[0]).strip()).expanduser().resolve()
                    dirp = Path(str(b_raw).strip()).expanduser().resolve()
                except OSError as e:
                    raise ValueError(
                        "invalid read_multiple base or nexa_permission_abs_targets[0]"
                    ) from e
                if dirp != ref:
                    raise ValueError(
                        "read_multiple_files base must match nexa_permission_abs_targets[0]"
                    )
            elif payload.get("base") and str(payload.get("base")).strip():
                try:
                    dirp = Path(str(payload["base"]).strip()).expanduser().resolve()
                except OSError as e:
                    raise ValueError("invalid read_multiple base path") from e
                try:
                    dirp.relative_to(root.resolve())
                except ValueError as e:
                    raise ValueError(
                        "read_multiple_files base must be under host_executor_work_root"
                    ) from e
            else:
                rel_base = (
                    payload.get("relative_path") or payload.get("relative_dir") or "."
                ).strip() or "."
                dirp = _safe_join_under_root(root, rel_base).resolve()

            _path_allowed_for_io(dirp)
            if not dirp.exists():
                raise ValueError(f"Base path does not exist: {dirp}")
            if not dirp.is_dir():
                if dirp.is_file():
                    raise ValueError(
                        f"{dirp} is a file, not a folder. Use \"read\" with that file path "
                        "instead of folder analysis."
                    )
                raise ValueError(f"Base path must be a directory: {dirp}")

            glob_pat = (payload.get("glob") or "*").strip()
            if len(glob_pat) > 120 or "/" in glob_pat or "\\" in glob_pat:
                raise ValueError("glob invalid for read_multiple_files")
            if glob_pat != "*" and not re.match(r"^[A-Za-z0-9_.*?\-\[\]]+$", glob_pat):
                raise ValueError("invalid glob pattern")

            collected: list[Path] = []
            for p in sorted(dirp.rglob(glob_pat), key=lambda x: str(x).lower()):
                if len(collected) >= max_files * 4:
                    break
                if not p.is_file():
                    continue
                if p.suffix.lower() not in ext_set:
                    continue
                collected.append(p)
                if len(collected) >= max_files:
                    break

            for fp in collected:
                try:
                    rel_disp = str(fp.resolve().relative_to(dirp)).replace("\\", "/")
                except ValueError:
                    continue
                if not add_file(rel_disp, fp):
                    break

        logger.info(
            "host_executor read_multiple_files parts=%s bytes_used=%s",
            len(chunks_out),
            bytes_used,
        )
        return _finalize_output(
            ("\n\n".join(chunks_out) if chunks_out else "(no files matched filters)")[: total_cap + 4000]
        )

    if action == "git_commit":
        msg = (payload.get("commit_message") or "").strip()
        if not msg or len(msg) > 240:
            raise ValueError("commit_message required, max 240 characters")
        if re.search(r"[`$;|&]", msg):
            raise ValueError("commit_message contains forbidden characters")
        code, out, err = _run_argv(["git", "add", "-A"], cwd=exec_root, timeout=60)
        if code != 0:
            return _finalize_output(f"git add failed (exit {code})\n{(out + err)[:4000]}")
        code2, out2, err2 = _run_argv(
            ["git", "commit", "-m", msg],
            cwd=exec_root,
            timeout=120,
        )
        tail = "\n".join(x for x in [out2, err2] if x.strip())
        logger.info("host_executor git_commit ok exit=%s", code2)
        if code2 != 0:
            return _finalize_output(f"git commit failed (exit {code2})\n{tail[:6000]}")
        return _finalize_output((tail or "Committed.")[:8000])

    if action == "git_push":
        argv = argv_for_git_push(payload)
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=min(timeout, 300))
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        logger.info("host_executor git_push ok exit=%s", code)
        if code != 0:
            return _finalize_output(f"git push failed (exit {code})\n{msg}"[:8000])
        return _finalize_output((msg or "Pushed.")[:8000])

    if action == "vercel_projects_list":
        code, out, err = _run_argv(
            ["vercel", "projects", "list"],
            cwd=exec_root,
            timeout=min(timeout, 120),
        )
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        if code != 0:
            return _finalize_output(f"vercel projects list failed (exit {code})\n{msg}"[:8000])
        return _finalize_output(msg[:8000] or "(empty)")

    if action == "vercel_remove":
        argv = argv_for_vercel_remove(payload)
        code, out, err = _run_argv(argv, cwd=exec_root, timeout=min(timeout, 180))
        msg = "\n".join(x for x in [out, f"STDERR:\n{err}" if err.strip() else ""] if x.strip())
        logger.info("host_executor vercel_remove ok exit=%s", code)
        if code != 0:
            return _finalize_output(f"vercel remove failed (exit {code})\n{msg}"[:8000])
        return _finalize_output((msg or "Removed.")[:8000])

    raise ValueError(
        f"unknown host_action {action!r}; try: plugin_skill, chain, git_status, run_command, file_read, file_write, "
        "git_commit, git_push, vercel_projects_list, vercel_remove, list_directory, find_files, "
        "read_multiple_files"
    )


def execute_host_executor_job(job: Any) -> str:
    """Entry point from local_tool_worker for ``host-executor`` jobs.

    Validation failures raise ``ValueError`` so the worker marks the job failed.
    """
    from app.core.db import SessionLocal
    from app.services.local_file_intel import maybe_finalize_intel_result

    db = SessionLocal()
    try:
        pl = dict(getattr(job, "payload_json", None) or {})
        raw = execute_payload(pl, db=db, job=job)
        return maybe_finalize_intel_result(pl, raw)
    finally:
        db.close()


def proposed_risk_level(payload: dict[str, Any]) -> str:
    """Suggest risk for UI / policy (all host-executor jobs still require approval in AgentJobService)."""
    action = (payload.get("host_action") or "").strip().lower()
    if action == "chain":
        return "high"
    if action in ("file_write", "git_commit", "git_push", "vercel_remove"):
        return "high"
    if action == "vercel_projects_list":
        return "normal"
    if action == "run_command":
        return "normal"
    if action in ("list_directory", "find_files"):
        return "low"
    if action == "read_multiple_files":
        return "normal"
    return "low"

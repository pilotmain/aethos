"""
On-demand local file intelligence — infer user intent only (no scanning, no indexing).

Maps natural language to allowlisted host_executor payloads. Paths are relative to
``host_executor_work_root`` when possible; absolute paths under that root are normalized.
Paths outside the work root use ``nexa_permission_abs_targets`` + ``base`` for
``read_multiple_files`` / ``list_directory`` (same source of truth as approval UI).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.custom_agent_routing import custom_agent_message_blocks_folder_heuristics
from app.services.host_executor_intent import safe_relative_path


def _agent_team_chat_blocks_folder_heuristics(text: str) -> bool:
    """Lazy import: avoids cycle with agent_team (chat → service → host bridge → local_file_intent)."""
    from app.services.agent_team.chat import agent_team_chat_blocks_folder_heuristics

    return agent_team_chat_blocks_folder_heuristics(text)

# Tokens that must never become synthetic paths like /app/my or folder targets for jobs.
GENERIC_PATH_WORDS: frozenset[str] = frozenset(
    {
        "my",
        "your",
        "the",
        "a",
        "an",
        "this",
        "that",
        "it",
        "local",
        "folder",
        "file",
        "files",
        "directory",
        "path",
        "project",
        "repo",
        "create",
        "agent",
        "custom",
        "summarize",
        "summarise",
        "analyze",
        "analyse",
        "please",
    }
)


def _first_segment_lower(path_candidate: str) -> str:
    s = (path_candidate or "").strip().strip("./")
    if not s:
        return ""
    seg = re.split(r"[\\/]", s.replace("\\", "/"), maxsplit=1)[0].lower()
    return seg.strip()


def _is_vague_path_guess(path_candidate: str) -> bool:
    """Single-token / generic fragments must not become host jobs or /app/<token>."""
    raw = (path_candidate or "").strip()
    if not raw:
        return True
    if "/" in raw or raw.startswith("~") or raw.startswith("."):
        return False
    if "\\" in raw:
        return False
    fl = _first_segment_lower(raw)
    if fl in GENERIC_PATH_WORDS:
        return True
    # Likely custom-agent handle (e.g. research-analyst), not a filesystem folder under work root.
    if "-" in raw and "/" not in raw and "\\" not in raw:
        return True
    return False


def _extract_path_fragment(line: str) -> str:
    """Best-effort path token from a user line (absolute, ~/, or relative segment)."""
    m = re.search(
        r"(/Users/[^\s]+|/home/[^\s]+|/private/var/[^\s]+|/tmp/[^\s]+|~/[^\s]+|\./[^\s]+)",
        line,
    )
    if m:
        return m.group(1).rstrip(".,;)")
    m2 = re.search(r"\b(?:in|under|at)\s+([\w.~][\w./~-]{1,400})", line, re.I)
    if m2:
        frag = m2.group(1).rstrip(".,;)")
        first_tok = (frag.split()[0] if frag else "").strip()
        seg0 = _first_segment_lower(first_tok)
        if seg0 in GENERIC_PATH_WORDS:
            return ""
        return frag
    # Generic Unix absolute path (e.g. /bad/path/file.txt) — not only /Users, /tmp, …
    m3 = re.search(r"(?:^|[\s\"'`])(/[^\s\"'`]+)", line)
    if m3:
        cand = (m3.group(1) or "").strip().rstrip(".,;)")
        if len(cand) > 1 and cand.startswith("/"):
            return cand
    return ""


@dataclass
class LocalFileIntent:
    """Result of :func:`infer_local_file_request`."""

    matched: bool
    payload: dict[str, Any] | None = None
    operation: str = "summarize"
    intel_question: str = ""
    path_resolution_failed: bool = False
    clarification_message: str | None = None
    clarification_axis: str | None = None  # "file" | "folder" | "neutral" when clarifying
    clarification_vague_path: bool = False
    error_message: str | None = None  # e.g. missing path on disk (explicit user path)
    directory_read_hint: bool = False  # existing dir + simple "read <path>" → guide user


_RE_COMPARE = re.compile(
    r"(?i)^(?:compare|diff)\s+(?:the\s+)?(?:files?\s+)?"
    r"([\w.`'\"/\-.]{1,240})\s+(?:and|vs\.?|with)\s+([\w.`'\"/\-.]{1,240})\s*\.?$"
)

_RE_FOLDER_VERB = re.compile(
    r"(?i)(?:check|summarize|analyse|analyze|explain|describe|overview|inspect|review"
    r"|read|look\s+(?:at|into)|what(?:'s| is)\s+in)\s+"
)

_RE_PATH_TAIL = re.compile(
    r"(?:folder|directory|project|path)?\s*[:.]?\s*"
    r"([\w~./\\-]{1,400})"
)

_RE_MD_ALL = re.compile(
    r"(?i)(?:read|open|summarize)\s+all\s+(?:markdown|md)\s+files?\s*(?:in\s+)?([\w~./\\-]{1,400})?"
)

_RE_FIND_KW = re.compile(
    r"(?i)find\s+files?\s+(?:mentioning|containing|with)\s+"
    r"['\"]?([^'\"\s]{1,80})['\"]?\s*(?:in\s+)?([\w~./\\-]{1,400})?"
)

_RE_STRUCTURE = re.compile(r"(?i)(explain|describe|show)\s+(?:the\s+)?(?:folder\s+)?structure")

# Explicit folder/list/search phrases — should not show "read a folder" clarification
_EXPLICIT_FOLDER_OR_LIST = re.compile(
    r"(?i)(analyze|analyse)\s+folder|list\s+files(?:\s+in|\s+from|\s+under)?|"
    r"read\s+files\s+in|summarize\s+files\s+in|find\s+files"
)

_MSG_FILE_CLARIFY = (
    "What file should I read? Please provide the full path, for example "
    "/Users/raya/lifeos/README.md."
)
_MSG_FOLDER_CLARIFY = (
    "Which folder should I read? Please provide the full path, for example /Users/raya/lifeos."
)
_MSG_NEUTRAL_CLARIFY = "What path should I use? Please provide a full file or folder path."
_VAGUE_PATH_SUFFIX = (
    " Use a real path on disk — not a generic word like “my” or a handle-like name."
)


def _missing_path_clarification_axis(line: str) -> str:
    """Prefer file vs folder vs neutral when the user omitted a usable path."""
    tl = (line or "").lower()
    has_folder_kw = bool(
        re.search(r"\b(folder|directory|project|repo|workspace)\b", tl)
    )
    has_file_word = bool(re.search(r"\bfile\b", tl))
    has_doc = bool(re.search(r"\b(document|documents)\b", tl))
    has_read_file_phrase = bool(re.search(r"\bread\s+(?:a\s+|the\s+|your\s+)?file\b", tl))
    has_local_file_phrase = "local file" in tl
    file_signal = (
        has_file_word or has_doc or has_read_file_phrase or has_local_file_phrase
    )
    if has_folder_kw and file_signal:
        return "folder"
    if file_signal and not has_folder_kw:
        return "file"
    if has_folder_kw and not file_signal:
        return "folder"
    return "neutral"


def _line_is_simple_read_verb(line: str) -> bool:
    """Leading read/show/cat/open (single-line folder heuristic gate)."""
    s = (line or "").strip()
    return bool(re.match(r"(?i)^(read|show|cat|open)\b", s))


def _clarify_read_existing_directory(line: str, path_guess: str) -> LocalFileIntent | None:
    """
    ``read /some/dir`` where ``some/dir`` exists as a directory → guide user (avoid file_read / huge reads).
    """
    if _EXPLICIT_FOLDER_OR_LIST.search(line):
        return None
    if not _line_is_simple_read_verb(line):
        return None
    try:
        p = Path(path_guess).expanduser().resolve()
    except OSError:
        return None
    if not p.exists() or not p.is_dir():
        return None
    disp = str(p)
    msg = (
        f"{disp} is a folder. Say **analyze folder {disp}** or **list files in {disp}** to continue."
    )
    return LocalFileIntent(
        matched=True,
        clarification_message=msg,
        clarification_axis="neutral",
        directory_read_hint=True,
    )


def _clarification_body_for_axis(axis: str, *, vague_path: bool) -> str:
    if axis == "file":
        msg = _MSG_FILE_CLARIFY
    elif axis == "folder":
        msg = _MSG_FOLDER_CLARIFY
    else:
        msg = _MSG_NEUTRAL_CLARIFY
    return msg + (_VAGUE_PATH_SUFFIX if vague_path else "")


def _norm_extensions_from_text(text: str) -> list[str] | None:
    t = text.lower()
    out: list[str] = []
    if "markdown" in t or ".md" in t or " md " in f" {t} ":
        out.append(".md")
    if "json" in t:
        out.append(".json")
    if "python" in t or ".py" in t:
        out.append(".py")
    if ".txt" in t or " text " in f" {t} ":
        out.append(".txt")
    return out if out else None


def _resolve_relative_path(raw: str) -> tuple[str | None, bool]:
    """
    Convert user path to path relative to host_executor_work_root.

    Returns (relative_path or None, failed_absolute_outside_root).
    """
    s = (raw or "").strip().strip("`\"'")
    if not s:
        return ".", False
    root = Path(get_settings().host_executor_work_root).expanduser().resolve()
    try:
        p = Path(s).expanduser().resolve()
    except OSError:
        return None, True
    try:
        rel = p.relative_to(root)
        sr = safe_relative_path(str(rel).replace("\\", "/"))
        return (sr if sr else "."), False
    except ValueError:
        pass
    sr2 = safe_relative_path(s.replace("\\", "/").lstrip("/"))
    if sr2:
        return sr2, False
    return None, True


def _read_multiple_intent_for_folder_path(
    path_raw: str,
    *,
    intel_op: str,
    intel_question: str,
    extensions: list[str] | None = None,
    keyword: str | None = None,
) -> LocalFileIntent:
    """``read_multiple_files`` for a folder path: inside work root (relative) or outside (abs targets)."""
    try:
        p_user = Path(path_raw).expanduser().resolve()
        p_root = Path(get_settings().host_executor_work_root).expanduser().resolve()
        try:
            p_user.relative_to(p_root)
            inside_root = True
        except ValueError:
            inside_root = False
    except OSError:
        disp = (path_raw or "").strip()[:2000]
        return LocalFileIntent(
            matched=True,
            error_message=f"Path does not exist: {disp}",
        )

    if not p_user.exists():
        disp = str(p_user)
        return LocalFileIntent(matched=True, error_message=f"Path does not exist: {disp}")

    if inside_root:
        rd, failed = _resolve_relative_path(path_raw)
        if rd is None or failed:
            return LocalFileIntent(matched=True, path_resolution_failed=True)
        full_inside = (p_root / rd).resolve()
        if not full_inside.exists():
            return LocalFileIntent(
                matched=True,
                error_message=f"Path does not exist: {full_inside}",
            )
        if full_inside.is_file():
            return LocalFileIntent(
                matched=True,
                error_message=(
                    f"{full_inside} is a file, not a folder. Use **read** with that file path "
                    "instead of folder analysis."
                ),
            )
        pl_in: dict[str, Any] = {
            "host_action": "read_multiple_files",
            "relative_path": rd,
            "base": str((p_root / rd).resolve()),
            "intel_analysis": True,
            "intel_operation": intel_op,
            "intel_question": intel_question,
        }
        if extensions:
            pl_in["extensions"] = extensions
        if keyword:
            pl_in["keyword"] = keyword
        return LocalFileIntent(
            matched=True,
            payload=pl_in,
            operation=intel_op,
            intel_question=intel_question,
        )

    if p_user.exists() and p_user.is_file():
        return LocalFileIntent(matched=True, path_resolution_failed=True)
    resolved = str(p_user)
    pl_out: dict[str, Any] = {
        "host_action": "read_multiple_files",
        "relative_path": ".",
        "nexa_permission_abs_targets": [resolved],
        "base": resolved,
        "intel_analysis": True,
        "intel_operation": intel_op,
        "intel_question": intel_question,
    }
    if extensions:
        pl_out["extensions"] = extensions
    if keyword:
        pl_out["keyword"] = keyword
    return LocalFileIntent(
        matched=True,
        payload=pl_out,
        operation=intel_op,
        intel_question=intel_question,
    )


def infer_local_file_request(
    user_text: str,
    *,
    default_relative_base: str = ".",
) -> LocalFileIntent:
    """
    Detect on-demand folder/file analysis requests (no background indexing).

    When matched, returns a payload suitable for merging into host_executor_json
    (typically ``read_multiple_files`` + intel flags).

    ``default_relative_base``: when the user omits a folder, use this path (relative to
    the host work root), e.g. active Nexa workspace project.
    """
    t = (user_text or "").strip()
    if not t or len(t) > 4_000:
        return LocalFileIntent(matched=False)

    if custom_agent_message_blocks_folder_heuristics(t) or _agent_team_chat_blocks_folder_heuristics(
        t
    ):
        return LocalFileIntent(matched=False)

    base = (default_relative_base or ".").strip() or "."

    line = t.splitlines()[0].strip()

    _RE_LIST_FILES = re.compile(
        r"(?i)\blist\s+(?:files?|folders?|dirs?|directories?)\s+(?:in|under|from)\s+([\w.`'\"/\-.~]{1,400})"
    )
    _RE_LS = re.compile(r"(?i)^ls\s+([\w.`'\"/\-.~]{1,400})\s*$")

    list_m = _RE_LIST_FILES.search(line)
    ls_m = _RE_LS.match(line) if not list_m else None
    path_raw = ""
    if list_m:
        path_raw = (list_m.group(1) or "").strip()
    elif ls_m:
        path_raw = (ls_m.group(1) or "").strip()
    if path_raw:
        try:
            p_user = Path(path_raw).expanduser().resolve()
            p_root = Path(get_settings().host_executor_work_root).expanduser().resolve()
            try:
                p_user.relative_to(p_root)
                inside_root = True
            except ValueError:
                inside_root = False
        except OSError:
            return LocalFileIntent(
                matched=True,
                error_message=f"Path does not exist: {(path_raw or '').strip()[:2000]}",
            )

        if not inside_root:
            if not p_user.exists():
                return LocalFileIntent(
                    matched=True,
                    error_message=f"Path does not exist: {p_user}",
                )
            return LocalFileIntent(
                matched=True,
                payload={
                    "host_action": "list_directory",
                    "relative_path": ".",
                    "nexa_permission_abs_targets": [str(p_user)],
                },
                operation="list",
                intel_question=t[:2000],
            )

        rd, failed = _resolve_relative_path(path_raw)
        if rd is None or failed:
            return LocalFileIntent(matched=True, path_resolution_failed=True)
        full_list = (p_root / rd).resolve()
        if not full_list.exists():
            return LocalFileIntent(
                matched=True,
                error_message=f"Path does not exist: {full_list}",
            )
        return LocalFileIntent(
            matched=True,
            payload={"host_action": "list_directory", "relative_path": rd},
            operation="list",
            intel_question=t[:2000],
        )

    _RE_LIST_DIRECT_ABS = re.compile(
        r"(?i)\blist\s+(?:files?|folders?|dirs?|directories?)\s+"
        r"(/Users/[^\s,;`\"']+|/home/[^\s,;`\"']+|/tmp/[^\s,;`\"']+|~/[^\s,;`\"']+)"
    )
    m_abs = _RE_LIST_DIRECT_ABS.search(line)
    if m_abs:
        alt_raw = (m_abs.group(1) or "").strip()
        inside_root = False
        p_user = None
        try:
            p_user = Path(alt_raw).expanduser().resolve()
            p_root = Path(get_settings().host_executor_work_root).expanduser().resolve()
            try:
                p_user.relative_to(p_root)
                inside_root = True
            except ValueError:
                inside_root = False
        except OSError:
            inside_root = False
            p_user = None
        if inside_root:
            rd2, failed2 = _resolve_relative_path(alt_raw)
            if rd2 is None or failed2:
                return LocalFileIntent(matched=True, path_resolution_failed=True)
            full_ls = (p_root / rd2).resolve()
            if not full_ls.exists():
                return LocalFileIntent(
                    matched=True,
                    error_message=f"Path does not exist: {full_ls}",
                )
            return LocalFileIntent(
                matched=True,
                payload={"host_action": "list_directory", "relative_path": rd2},
                operation="list",
                intel_question=t[:2000],
            )
        if p_user is not None:
            if not p_user.exists():
                return LocalFileIntent(
                    matched=True,
                    error_message=f"Path does not exist: {p_user}",
                )
            return LocalFileIntent(
                matched=True,
                payload={
                    "host_action": "list_directory",
                    "relative_path": ".",
                    "nexa_permission_abs_targets": [str(p_user)],
                },
                operation="list",
                intel_question=t[:2000],
            )

    # Compare two files
    mc = _RE_COMPARE.match(line)
    if mc:
        a_raw, b_raw = mc.group(1), mc.group(2)
        ra, fa = _resolve_relative_path(a_raw)
        rb, fb = _resolve_relative_path(b_raw)
        if ra is None or rb is None or fa or fb:
            return LocalFileIntent(matched=True, path_resolution_failed=True)
        return LocalFileIntent(
            matched=True,
            payload={
                "host_action": "read_multiple_files",
                "relative_paths": [ra, rb],
                "intel_analysis": True,
                "intel_operation": "compare",
                "intel_question": t[:2000],
            },
            operation="compare",
            intel_question=t[:2000],
        )

    # Find keyword in folder
    mf = _RE_FIND_KW.match(line)
    if mf:
        kw = (mf.group(1) or "").strip()
        dir_raw = (mf.group(2) or "").strip() or base
        return _read_multiple_intent_for_folder_path(
            dir_raw,
            intel_op="search",
            intel_question=t[:2000],
            keyword=kw,
        )

    # All markdown in folder
    mm = _RE_MD_ALL.match(line)
    if mm:
        dir_raw = (mm.group(1) or "").strip() or base
        return _read_multiple_intent_for_folder_path(
            dir_raw,
            intel_op="summarize",
            intel_question=t[:2000],
            extensions=[".md", ".markdown"],
        )

    intel_op = "summarize"
    if _RE_STRUCTURE.search(line):
        intel_op = "structure"

    # Broad folder requests: verb + path
    if _RE_FOLDER_VERB.search(line) or intel_op == "structure":
        path_guess = _extract_path_fragment(line)
        if not path_guess:
            mf_abs = re.search(r"(?i)\b(?:folder|directory|project)\s+(/\S+)", line)
            if mf_abs:
                path_guess = (mf_abs.group(1) or "").strip().rstrip(".,;)")
        # Do not use a loose "tail" regex: it matches the first word (e.g. "read" from
        # "read files in my local folder") and creates bogus /app/<token> jobs.
        if not path_guess and intel_op == "structure":
            path_guess = base
        if not path_guess:
            ax = _missing_path_clarification_axis(line)
            return LocalFileIntent(
                matched=True,
                clarification_message=_clarification_body_for_axis(ax, vague_path=False),
                clarification_axis=ax,
            )
        if _is_vague_path_guess(path_guess):
            ax = _missing_path_clarification_axis(line)
            return LocalFileIntent(
                matched=True,
                clarification_message=_clarification_body_for_axis(ax, vague_path=True),
                clarification_axis=ax,
                clarification_vague_path=True,
            )
        dir_hint = _clarify_read_existing_directory(line, path_guess)
        if dir_hint is not None:
            return dir_hint
        exts = _norm_extensions_from_text(t)
        return _read_multiple_intent_for_folder_path(
            path_guess,
            intel_op=intel_op,
            intel_question=t[:2000],
            extensions=exts,
        )

    return LocalFileIntent(matched=False)

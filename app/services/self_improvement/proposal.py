"""
Phase 73b — Self-improvement proposal generator + validator + persistence.

Pipeline:

1. **Generate** — :func:`generate_proposal_diff` calls
   :func:`app.services.llm.completion.primary_complete_messages` with
   ``task_type="self_improvement_diff"`` so the cost-aware router from
   Phase 72 picks the right model. The prompt instructs the LLM to return
   **exactly one unified diff**, nothing else.
2. **Validate** — :func:`validate_proposal_diff` parses the unified diff
   with a minimal hand-rolled parser (no new deps), enforces the allowlist
   from :mod:`app.services.self_improvement.context`, caps the file count
   and total +/- line count, and runs a regex sweep for obvious secrets in
   the added lines.
3. **Persist** — :class:`ProposalStore` writes to a new
   ``self_improvement_proposals`` table inside the existing
   ``data/agent_audit.db`` SQLite database (same location pattern as
   :mod:`app.services.agent.learning` so we don't introduce a second SQLite
   file).

No code is ever applied to disk from this module — that's the API layer's
job (and only after sandbox + owner approval).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from app.core.config import get_settings
from app.services.llm.completion import Message, primary_complete_messages
from app.services.self_improvement.context import (
    CodeContext,
    fetch_context,
    is_path_allowed,
    normalize_relpath,
)

logger = logging.getLogger(__name__)


# --- Status constants ------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_APPLIED = "applied"
STATUS_REVERTED = "reverted"

VALID_STATUSES = {STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_APPLIED, STATUS_REVERTED}


# --- Validator constants ---------------------------------------------------

# Regex sweep for obvious secrets in *added* diff lines. Deliberately
# conservative — we'd rather be noisy than ship a leaked key. Patterns are
# matched case-insensitive against the line *after* the leading ``+``.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[A-Za-z0-9]{20,}"),  # OpenAI / Anthropic style
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{12,}"),  # AWS access key id
    re.compile(r"(?i)aws_secret_access_key\s*=\s*['\"]?[A-Za-z0-9/+=]{30,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)password\s*=\s*['\"][^'\"]{6,}['\"]"),
    re.compile(r"(?i)api[_-]?key\s*=\s*['\"][^'\"]{16,}['\"]"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),  # GitHub PAT
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
)


# --- Data classes ----------------------------------------------------------


@dataclass
class DiffFile:
    """One file's worth of changes inside a unified diff."""

    path: str
    added_lines: int = 0
    removed_lines: int = 0
    is_new: bool = False
    is_delete: bool = False


@dataclass
class ValidationResult:
    """Outcome of :func:`validate_proposal_diff`."""

    ok: bool
    files: list[DiffFile] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    total_added: int = 0
    total_removed: int = 0


@dataclass
class Proposal:
    """A persisted proposal row."""

    id: str
    title: str
    problem_statement: str
    target_paths: list[str]
    diff: str
    status: str
    rationale: str | None
    created_by: str | None
    created_at: str
    sandbox_result: dict[str, Any] | None
    applied_commit_sha: str | None
    reverted_commit_sha: str | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


# --- Diff parsing ----------------------------------------------------------


_DIFF_HEADER_RX = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)\s*$")
_NEW_FILE_RX = re.compile(r"^new file mode \d+\s*$")
_DELETED_FILE_RX = re.compile(r"^deleted file mode \d+\s*$")
_MINUS_FILE_RX = re.compile(r"^---\s+(?:a/)?(?P<p>.+?)\s*$")
_PLUS_FILE_RX = re.compile(r"^\+\+\+\s+(?:b/)?(?P<p>.+?)\s*$")
_HUNK_RX = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+\d+(?:,\d+)?\s+@@")


def parse_unified_diff(diff: str) -> list[DiffFile]:
    """Parse a unified diff into a list of :class:`DiffFile`.

    This is intentionally minimal — it understands ``diff --git`` headers,
    ``new file`` / ``deleted file`` markers, ``---`` / ``+++`` paths, and
    counts ``+`` / ``-`` lines inside each hunk. Hunks without a preceding
    ``diff --git`` header are skipped (we won't apply such diffs anyway).
    """
    files: list[DiffFile] = []
    current: DiffFile | None = None
    in_hunk = False
    for raw_line in (diff or "").splitlines():
        line = raw_line.rstrip("\r")
        m = _DIFF_HEADER_RX.match(line)
        if m:
            target = m.group("b")
            current = DiffFile(path=target)
            files.append(current)
            in_hunk = False
            continue
        if current is None:
            continue
        if _NEW_FILE_RX.match(line):
            current.is_new = True
            continue
        if _DELETED_FILE_RX.match(line):
            current.is_delete = True
            continue
        m = _MINUS_FILE_RX.match(line)
        if m and m.group("p") != "/dev/null":
            in_hunk = False
            continue
        m = _PLUS_FILE_RX.match(line)
        if m:
            if m.group("p") != "/dev/null":
                # ``+++`` is the authoritative target path for the file
                current.path = m.group("p")
            in_hunk = False
            continue
        if _HUNK_RX.match(line):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current.added_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.removed_lines += 1
    return files


def _added_lines(diff: str) -> Iterable[str]:
    """Yield only the *content* of added lines (without the leading ``+``)."""
    in_hunk = False
    for raw_line in (diff or "").splitlines():
        line = raw_line.rstrip("\r")
        if _HUNK_RX.match(line):
            in_hunk = True
            continue
        if line.startswith("---") or line.startswith("+++") or line.startswith("diff --git"):
            in_hunk = False
            continue
        if in_hunk and line.startswith("+") and not line.startswith("+++"):
            yield line[1:]


# --- Validator -------------------------------------------------------------


def validate_proposal_diff(diff: str) -> ValidationResult:
    """
    Validate a unified diff against Phase 73b's hard rules. Returns a
    :class:`ValidationResult` whose ``ok`` field is True only if every
    rule passes; otherwise ``errors`` lists each violation (caller can
    surface them in the API response / UI).
    """
    settings = get_settings()
    max_files = max(1, int(getattr(settings, "nexa_self_improvement_max_files_per_proposal", 5) or 5))
    max_lines = max(1, int(getattr(settings, "nexa_self_improvement_max_diff_lines", 400) or 400))

    result = ValidationResult(ok=True)
    if not diff or not diff.strip():
        result.ok = False
        result.errors.append("empty_diff")
        return result

    files = parse_unified_diff(diff)
    if not files:
        result.ok = False
        result.errors.append("no_diff_headers_found")
        return result
    result.files = files

    if len(files) > max_files:
        result.ok = False
        result.errors.append(
            f"too_many_files:{len(files)}>max_{max_files}"
        )

    total_added = sum(f.added_lines for f in files)
    total_removed = sum(f.removed_lines for f in files)
    result.total_added = total_added
    result.total_removed = total_removed
    if (total_added + total_removed) > max_lines:
        result.ok = False
        result.errors.append(
            f"diff_too_large:{total_added}+/{total_removed}->max_{max_lines}_combined"
        )
    # No-op diff guard: if the diff parses but has zero adds/removes, reject.
    if total_added == 0 and total_removed == 0:
        result.ok = False
        result.errors.append("no_op_diff")
    # Scorched-earth guard: deletions with zero adds in a non-delete file.
    if total_removed > 0 and total_added == 0 and not all(f.is_delete for f in files):
        result.ok = False
        result.errors.append("pure_deletion_without_replacement")

    for f in files:
        try:
            norm = normalize_relpath(f.path)
        except Exception as exc:  # noqa: BLE001
            result.ok = False
            result.errors.append(f"bad_path:{f.path}:{exc}")
            continue
        if not is_path_allowed(norm):
            result.ok = False
            result.errors.append(f"path_not_allowed:{norm}")
        f.path = norm

    for added in _added_lines(diff):
        for rx in _SECRET_PATTERNS:
            if rx.search(added):
                result.ok = False
                result.errors.append(f"secret_pattern_in_added_line:{rx.pattern[:48]}")
                break

    return result


# --- LLM-driven generation -------------------------------------------------


_DIFF_FENCE_RX = re.compile(r"```(?:diff)?\n([\s\S]*?)```", re.MULTILINE)


def _strip_diff_fence(text: str) -> str:
    """If the LLM wrapped the diff in a Markdown fence, peel it off."""
    if not text:
        return ""
    m = _DIFF_FENCE_RX.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def _build_generation_prompt(
    *,
    problem_statement: str,
    contexts: list[CodeContext],
    target_paths: list[str],
) -> list[Message]:
    target_block = "\n".join(f"- {p}" for p in target_paths) or "(none specified)"
    context_block_parts: list[str] = []
    for c in contexts:
        context_block_parts.append(f"--- BEGIN FILE: {c.path} ---\n{c.content}\n--- END FILE: {c.path} ---")
    context_block = "\n\n".join(context_block_parts) if context_block_parts else "(no file context attached)"

    system = (
        "You are an AethOS self-improvement code reviewer. You are given a "
        "problem statement and a small set of files from the running system. "
        "Your job is to produce a unified diff (and ONLY a unified diff) that "
        "fixes or improves the code. Constraints:\n"
        "1. Output exactly one unified diff in standard `diff --git a/X b/X` "
        "format with `---`/`+++` and `@@` hunks. No prose, no fences, no headers.\n"
        "2. Touch only the files explicitly listed in TARGET PATHS. Do not "
        "introduce new files unless absolutely necessary.\n"
        "3. Keep changes minimal and surgical. Do not reformat unrelated lines.\n"
        "4. NEVER include secrets, API keys, tokens, or hardcoded passwords.\n"
        "5. Preserve existing tests and public function signatures unless the "
        "problem statement explicitly calls for changing them.\n"
        "If you cannot produce a safe diff, output exactly the single line "
        "`# NO_DIFF_AVAILABLE` and nothing else."
    )
    user = (
        f"PROBLEM STATEMENT:\n{problem_statement.strip()}\n\n"
        f"TARGET PATHS:\n{target_block}\n\n"
        f"FILE CONTEXT:\n{context_block}\n\n"
        "Now output the unified diff."
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def generate_proposal_diff(
    *,
    problem_statement: str,
    target_paths: list[str],
    extra_context_paths: list[str] | None = None,
    budget_member_id: str | None = None,
    budget_member_name: str | None = None,
) -> tuple[str, list[CodeContext]]:
    """
    Ask the LLM to generate a unified diff for ``problem_statement``.

    Returns a tuple of ``(diff_text, attached_contexts)``. The diff is the
    raw string from the LLM with any Markdown fence stripped — it is
    **not** validated here; callers must run :func:`validate_proposal_diff`
    on the result before persisting / applying.

    Raises :class:`ValueError` if no target paths pass the allowlist (so the
    LLM never sees forbidden paths in the prompt).
    """
    cleaned_targets: list[str] = []
    for p in target_paths or []:
        norm = normalize_relpath(p)
        if not is_path_allowed(norm):
            raise ValueError(f"target_path_not_allowed:{norm}")
        cleaned_targets.append(norm)
    if not cleaned_targets:
        raise ValueError("no_valid_target_paths")

    extras: list[str] = []
    for p in extra_context_paths or []:
        try:
            norm = normalize_relpath(p)
            if is_path_allowed(norm) and norm not in cleaned_targets:
                extras.append(norm)
        except Exception:  # noqa: BLE001
            continue

    contexts: list[CodeContext] = []
    for p in cleaned_targets + extras:
        try:
            contexts.append(fetch_context(p))
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_context failed for %s: %s", p, exc)

    messages = _build_generation_prompt(
        problem_statement=problem_statement,
        contexts=contexts,
        target_paths=cleaned_targets,
    )
    raw = primary_complete_messages(
        messages,
        task_type="self_improvement_diff",
        max_tokens=4096,
        temperature=0.0,
        budget_member_id=budget_member_id,
        budget_member_name=budget_member_name,
    )
    diff_text = _strip_diff_fence(raw or "")
    return diff_text, contexts


# --- Persistence -----------------------------------------------------------


class ProposalStore:
    """SQLite-backed store for self-improvement proposals.

    Lives inside the existing ``data/agent_audit.db`` so we don't introduce
    a second database file. Schema is created lazily and is idempotent.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS self_improvement_proposals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            problem_statement TEXT NOT NULL,
            target_paths TEXT NOT NULL,        -- JSON array of strings
            diff TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            rationale TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            sandbox_result TEXT,                -- JSON blob from sandbox.run()
            sandbox_run_at TEXT,
            applied_commit_sha TEXT,
            reverted_commit_sha TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            settings = get_settings()
            root = Path(getattr(settings, "nexa_data_dir", "") or "data")
            db_path = root / "agent_audit.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(self._SCHEMA)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_si_proposals_status "
                "ON self_improvement_proposals(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_si_proposals_created_at "
                "ON self_improvement_proposals(created_at)"
            )

    def _row_to_proposal(self, r: sqlite3.Row) -> Proposal:
        try:
            paths = json.loads(r["target_paths"]) if r["target_paths"] else []
            if not isinstance(paths, list):
                paths = []
        except Exception:
            paths = []
        try:
            sb = json.loads(r["sandbox_result"]) if r["sandbox_result"] else None
        except Exception:
            sb = None
        return Proposal(
            id=str(r["id"]),
            title=r["title"],
            problem_statement=r["problem_statement"],
            target_paths=[str(p) for p in paths],
            diff=r["diff"] or "",
            status=r["status"],
            rationale=r["rationale"],
            created_by=r["created_by"],
            created_at=r["created_at"],
            sandbox_result=sb,
            applied_commit_sha=r["applied_commit_sha"],
            reverted_commit_sha=r["reverted_commit_sha"],
        )

    def create(
        self,
        *,
        title: str,
        problem_statement: str,
        target_paths: list[str],
        diff: str,
        rationale: str | None = None,
        created_by: str | None = None,
    ) -> Proposal:
        proposal_id = uuid.uuid4().hex[:16]
        target_blob = json.dumps([str(p) for p in target_paths])
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO self_improvement_proposals
                    (id, title, problem_statement, target_paths, diff,
                     status, rationale, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal_id,
                    (title or "").strip()[:256] or "(untitled)",
                    problem_statement.strip(),
                    target_blob,
                    diff,
                    STATUS_PENDING,
                    rationale,
                    created_by,
                ),
            )
        got = self.get(proposal_id)
        if got is None:  # pragma: no cover — insert + immediate read should always succeed
            raise RuntimeError("proposal_insert_failed")
        return got

    def get(self, proposal_id: str) -> Proposal | None:
        if not proposal_id:
            return None
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT * FROM self_improvement_proposals WHERE id = ?",
                (proposal_id,),
            )
            row = cur.fetchone()
        return self._row_to_proposal(row) if row else None

    def list_proposals(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Proposal]:
        limit = max(1, min(int(limit or 50), 200))
        with self._lock, self._connect() as conn:
            if status:
                cur = conn.execute(
                    "SELECT * FROM self_improvement_proposals "
                    "WHERE status = ? ORDER BY datetime(created_at) DESC LIMIT ?",
                    (status, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM self_improvement_proposals "
                    "ORDER BY datetime(created_at) DESC LIMIT ?",
                    (limit,),
                )
            rows = cur.fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def set_status(
        self,
        proposal_id: str,
        new_status: str,
        *,
        applied_commit_sha: str | None = None,
        reverted_commit_sha: str | None = None,
    ) -> Proposal | None:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"invalid_status:{new_status}")
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE self_improvement_proposals
                SET status = ?,
                    applied_commit_sha = COALESCE(?, applied_commit_sha),
                    reverted_commit_sha = COALESCE(?, reverted_commit_sha),
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (new_status, applied_commit_sha, reverted_commit_sha, proposal_id),
            )
        return self.get(proposal_id)

    def record_sandbox_result(
        self,
        proposal_id: str,
        result: dict[str, Any],
    ) -> Proposal | None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE self_improvement_proposals
                SET sandbox_result = ?,
                    sandbox_run_at = datetime('now'),
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (json.dumps(result, default=str), proposal_id),
            )
        return self.get(proposal_id)

    def get_sandbox_run_age_seconds(self, proposal_id: str) -> float | None:
        """How long ago (in seconds) the sandbox last ran for this proposal."""
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "SELECT sandbox_run_at FROM self_improvement_proposals WHERE id = ?",
                (proposal_id,),
            )
            row = cur.fetchone()
        if not row or not row["sandbox_run_at"]:
            return None
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT (julianday('now') - julianday(?)) * 86400.0 AS secs",
                    (row["sandbox_run_at"],),
                )
                got = cur.fetchone()
                return float(got["secs"]) if got and got["secs"] is not None else None
        except Exception:  # noqa: BLE001
            return None


# --- Singleton accessor ----------------------------------------------------

_proposal_store: ProposalStore | None = None


def get_proposal_store() -> ProposalStore:
    global _proposal_store
    if _proposal_store is None:
        _proposal_store = ProposalStore()
    return _proposal_store


__all__ = [
    "DiffFile",
    "Proposal",
    "ProposalStore",
    "STATUS_APPLIED",
    "STATUS_APPROVED",
    "STATUS_PENDING",
    "STATUS_REJECTED",
    "STATUS_REVERTED",
    "ValidationResult",
    "VALID_STATUSES",
    "generate_proposal_diff",
    "get_proposal_store",
    "parse_unified_diff",
    "validate_proposal_diff",
]

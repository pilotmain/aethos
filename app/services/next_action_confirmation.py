"""
Parse 'yes' / 'first' / 'option 2' and map to stored co-pilot next steps. Chat-first, no new UI.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SUGGESTED_TTL_SECONDS = 30 * 60

# Commands we inject directly; free-text lines get a one-time "run" confirm.
_INJECTABLE = re.compile(
    r"^\s*("
    r"@[A-Za-z][A-Za-z0-9_]*\b"  # @marketing, @dev, …
    r"|/[A-Za-z][A-Za-z0-9_]*"  # /doc, /improve, /dev, …
    r")",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SuggestedAction:
    index: int
    label: str
    command: str
    risk: str
    created_at: str

    @staticmethod
    def from_dict(d: dict[str, Any]) -> SuggestedAction | None:
        try:
            return SuggestedAction(
                index=int(d.get("index", 0)),
                label=str(d.get("label") or ""),
                command=str(d.get("command") or ""),
                risk=str(d.get("risk") or "low"),
                created_at=str(d.get("created_at") or ""),
            )
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class NextActionUserTurn:
    """Result of interpreting a user line against stored suggestions or pending 'run' state."""

    immediate_assistant: str | None = None
    reprocess_user_text: str | None = None
    store_pending_command: str | None = None
    clear_suggestions: bool = False
    no_match: bool = False  # not applicable; caller should continue normal flow
    # Trust line: prepend to the pipeline reply (Telegram + Web) when reprocess_user_text is set
    ack_line: str | None = None


def command_from_suggestion_line(line: str) -> str:
    """Strip list markup; take actionable text (first line)."""
    s = (line or "").strip()
    s = re.sub(r"^[-*•]\s+", "", s)
    s = re.sub(r"^option\s+", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\d+[.)]\s+", "", s)
    s = s.splitlines()[0] if s else ""
    return s.strip()[:1_200]


def is_injectable_command(cmd: str) -> bool:
    c = (cmd or "").strip()
    if not c:
        return False
    return bool(_INJECTABLE.match(c))


def risk_for_suggestion_command(cmd: str) -> str:
    t = (cmd or "").strip().lower()
    if t.startswith(("@dev",)) or t.startswith(("/improve", "/dev")) or (
        "queue" in t and "job" in t
    ):
        return "high"
    if t.startswith(("@ops",)) or t.startswith("/ops"):
        return "medium"
    if is_injectable_command(cmd):
        return "low"
    return "unknown"


def parse_suggested_actions_from_context(raw: str | None) -> list[SuggestedAction]:
    if not (raw or "").strip():
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    out: list[SuggestedAction] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        a = SuggestedAction.from_dict(item)
        if a and a.index >= 1 and a.command:
            out.append(a)
    return sorted(out, key=lambda x: x.index)[:4]


def _is_expired(actions: list[SuggestedAction], now: datetime) -> bool:
    if not actions:
        return True
    ts0 = (actions[0].created_at or "").strip()
    if not ts0:
        return False
    try:
        t = datetime.fromisoformat(ts0.replace("Z", "+00:00"))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() > SUGGESTED_TTL_SECONDS


def _only_digits_choice(t: str) -> int | None:
    """1–4 only; a bare digit 5+ is not treated as a selection (avoids clashing with unrelated '5' messages)."""
    s = t.strip()
    m = re.fullmatch(r"([1-9])", s)
    if m:
        return int(m.group(1))
    return None


def _ordinal_index(t: str) -> int | None:
    low = t.lower().strip()
    word_only = re.fullmatch(r"(first|second|third|fourth)", low)
    if word_only:
        return {"first": 1, "second": 2, "third": 3, "fourth": 4}[word_only.group(1)]
    i = re.IGNORECASE
    pairs: list[tuple[re.Pattern[str], int]] = [
        (re.compile(r"\bthe\s+first(\s+(one|thing|item|option|step|suggestion|choice|line))?\b", i), 1),
        (re.compile(r"\bsecond(\s+(one|thing|item|option|step|suggestion|choice|line))?\b", i), 2),
        (re.compile(r"\bthird(\s+(one|thing|item|option|step|suggestion|choice|line))?\b", i), 3),
        (re.compile(r"\bfourth(\s+(one|thing|item|option|step|suggestion|choice|line))?\b", i), 4),
        (re.compile(r"\b1st\b", i), 1),
        (re.compile(r"\b2nd\b", i), 2),
        (re.compile(r"\b3rd\b", i), 3),
        (re.compile(r"\b4th\b", i), 4),
    ]
    for p, n in pairs:
        if p.search(low):
            return n
    m2 = re.search(
        r"(?:^|\b)(option|#|number|no\.?|num\.?|run(?:\s+number)?|choice)\s*#?\s*([1-4])\b",
        low,
        flags=re.IGNORECASE,
    ) or re.search(
        r"run (?:#|number)?\s*([1-4])\b", low, flags=re.IGNORECASE
    )
    if m2 and m2.lastindex:
        g = m2.group(m2.lastindex)
        if g and g.isdigit():
            return int(g)
    return None


def _wants_yesish(t: str) -> bool:
    low = t.lower().strip()
    return bool(
        re.search(
            r"^(y(es)?\b|yep|yeah|sure|let'?s (do|go)\b|do (it|that|this)\b|go( ahead| for it)\b|"
            r"sounds? good|go for it)[\s!.?]*$",
            low,
        )
    )

def _wants_proceed_ok(t: str) -> bool:
    """'ok' / 'k' that might confirm the single next step (avoid matching unrelated ok)."""
    low = t.lower().strip()
    if low in ("ok", "okay", "k", "kk", "okey"):
        return True
    return bool(re.match(r"^ok(ay|ey)?[!.]*$", low, flags=re.IGNORECASE))

def _only_run_word(t: str) -> bool:
    return bool(re.match(r"^run[!.]*$", t.strip(), flags=re.IGNORECASE))


def ack_line_for_injected_command(cmd: str) -> str:
    """User-visible line before the main pipeline runs (Nexa co-pilot / next-step)."""
    c = (cmd or "").strip()
    if not c:
        return "Running next step (using your last pending line)."
    if "\n" in c or len(c) > 220:
        short = c[:600] + ("…" if len(c) > 600 else "")
        return f"Running next step:\n{short}"
    return f"Running next step: {c[:1_200]}"


def _parse_last_injected(pending_json: str | None) -> tuple[str, str] | None:
    if not (pending_json or "").strip():
        return None
    try:
        o = json.loads(pending_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(o, dict):
        return None
    c = str(o.get("command") or "").strip()
    ts0 = str(o.get("created_at") or "")
    if not c:
        return None
    return c, ts0


def is_last_injected_action_expired(
    last_injected_json: str | None, *, now: datetime | None = None
) -> bool:
    now = now or datetime.now(timezone.utc)
    t = _parse_last_injected(last_injected_json)
    if t is None:
        return True
    _, ts0 = t
    if not (ts0 or "").strip():
        return False
    try:
        tdt = datetime.fromisoformat(ts0.replace("Z", "+00:00"))
    except ValueError:
        return True
    if tdt.tzinfo is None:
        tdt = tdt.replace(tzinfo=timezone.utc)
    return (now - tdt).total_seconds() > SUGGESTED_TTL_SECONDS


def _wants_action_repeat_phrase(t: str) -> bool:
    s = t.lower().strip()
    if s in (
        "again",
        "same",
        "one more",
        "one more time",
        "do it again",
        "do that again",
        "run it again",
        "run that again",
        "same thing",
        "same again",
    ):
        return True
    return bool(
        re.match(
            r"^(do|run) (it|that) again[!.?]*$|"
            r"^repeat( that)?[!.?]*$|^one more( time)?[!.?]*$|"
            r"^same (thing|again|one)?[!.?]*$",
            s,
        )
    )


def _agent_slug_for_action(a: SuggestedAction) -> str | None:
    for raw in ((a.command or ""), a.label or ""):
        s = (raw or "").strip()
        if not s:
            continue
        m = re.match(r"^\s*@([A-Za-z][A-Za-z0-9_]*)\b", s)
        if m:
            return m.group(1).lower()
        m2 = re.search(r"@[A-Za-z][A-Za-z0-9_]*\b", a.command or "")
        if m2:
            w = m2.group(0)
            return w[1:].lower() if w.startswith("@") else w.lower()
        m3 = re.match(r"^\s*/\s*([A-Za-z][A-Za-z0-9_-]*)\b", s, re.I)
        if m3:
            return m3.group(1).lower()
    return None


def _word_overlap_score(user_text: str, a: SuggestedAction) -> int:
    stop = {
        "the", "and", "for", "you", "not", "how", "one", "can", "run", "doc", "get",
        "out", "use", "from", "with", "this", "that", "are", "was", "our", "has",
        "all", "any", "per", "into", "what", "when", "its", "who", "too",
    }
    uws = re.findall(r"[a-z0-9_]{4,}", user_text.lower())
    uws = [w for w in uws if w not in stop]
    blob = f"{a.label} {a.command}".lower()
    return sum(1 for w in uws if w in blob)


def _match_suggestion_by_natural_cue(
    t: str, valid: list[SuggestedAction]
) -> SuggestedAction | None:
    """'do the marketing one' → @slug; unique 4+ letter overlap as fallback when clear."""
    if not valid:
        return None
    if re.fullmatch(r"\s*[1-4]\s*", t or ""):
        return None
    m1 = re.search(
        r"(?i)(?:\bdo\s+the|\brun\s+the)\s+([a-z0-9_][a-z0-9_]*)\s+"
        r"(one|thing|item|option|line|step|suggestion|choice)\b",
        t,
    )
    m2 = re.search(
        r"(?i)(?<!\bfirst )(?<!\bsecond )(?<!\bthird )(?<!\bfourth )\bthe\s+"
        r"([a-z0-9_][a-z0-9_]*)\s+"
        r"(one|thing|item|option|line|step|suggestion|choice)\b",
        t,
    )
    m_alt = re.search(
        r"(?i)(?:\bpick|\buse|\bgo\s+with)(?:\s+the)?\s+@?([a-z0-9_]+)\b", t
    )
    m0 = m1 or m2 or m_alt
    if m0:
        cue = m0.group(1).lower()
        if cue in {
            "first", "second", "third", "fourth", "1st", "2nd", "3rd", "4th", "next", "last", "a",
        }:
            return None
        by_slug: list[SuggestedAction] = []
        for a in valid:
            slug = _agent_slug_for_action(a)
            if not slug:
                continue
            if (
                cue == slug
                or slug.startswith(cue)
                or (3 <= len(cue) < len(slug) and cue in slug)
            ):
                by_slug.append(a)
        if len(by_slug) == 1:
            return by_slug[0]
        if len(cue) >= 4:
            in_cue = [a for a in valid if cue in f"{a.label} {a.command}".lower()]
            if len(in_cue) == 1:
                return in_cue[0]
    if len(valid) < 2:
        return None
    best_s = -1
    best_a: SuggestedAction | None = None
    for a in valid:
        s0 = _word_overlap_score(t, a)
        if s0 > best_s:
            best_s, best_a = s0, a
    if best_s < 2 or best_a is None:
        return None
    n_at_best = len({x for x in valid if _word_overlap_score(t, x) == best_s})
    return best_a if n_at_best == 1 else None


def interpret_next_action_user_message(
    user_text: str,
    actions: list[SuggestedAction],
    pending_json: str | None,
    last_injected_json: str | None = None,
    *,
    now: datetime | None = None,
) -> NextActionUserTurn:
    """
    Interpret user line against last suggestions and optional pending 'run' gate for unknown commands.
    """
    now = now or datetime.now(timezone.utc)
    t = (user_text or "").strip()
    if not t:
        return NextActionUserTurn(no_match=True)

    pcmd0 = _parse_pending_command(pending_json)
    if pcmd0 and is_pending_inject_expired(pending_json):
        return NextActionUserTurn(
            immediate_assistant=(
                "I don’t have a recent next step to continue. Tell me what you want to do next, "
                "or ask in your own words."
            ),
            clear_suggestions=True,
        )
    if pcmd0 and (_only_run_word(t) or _wants_action_repeat_phrase(t)):
        return NextActionUserTurn(
            reprocess_user_text=pcmd0,
            clear_suggestions=True,
            ack_line=ack_line_for_injected_command(pcmd0),
        )

    if (not pcmd0) and _wants_action_repeat_phrase(t):
        lastp = _parse_last_injected(last_injected_json)
        if not lastp:
            return NextActionUserTurn(
                immediate_assistant="Nothing to repeat yet — pick a “Next step” or tell me what to do.",
            )
        last_cmd, _last_ts = lastp
        if is_last_injected_action_expired(last_injected_json, now=now):
            return NextActionUserTurn(
                immediate_assistant=(
                    "That was a while ago — I don’t have a fresh action to repeat. "
                    "Pick a new next step or describe what you want."
                ),
                clear_suggestions=True,
            )
        return NextActionUserTurn(
            reprocess_user_text=last_cmd,
            clear_suggestions=True,
            ack_line=ack_line_for_injected_command(last_cmd),
        )

    if not actions and not pcmd0:
        return NextActionUserTurn(no_match=True)

    if not actions and pcmd0 and not _only_run_word(t) and not _wants_action_repeat_phrase(t):
        return NextActionUserTurn(no_match=True)

    # Expired: only react to “continuation” / confirm phrasing, not every chat
    if _is_expired(actions, now) and (not pcmd0):
        looks_like_continuation = (
            _wants_yesish(t)
            or _wants_proceed_ok(t)
            or _only_digits_choice(t) is not None
            or _ordinal_index(t) is not None
        )
        if looks_like_continuation:
            return NextActionUserTurn(
                immediate_assistant=(
                    "I don’t have a recent next step to continue. Tell me what you want to do next, "
                    "or ask in your own words."
                ),
                clear_suggestions=True,
            )
        return NextActionUserTurn(no_match=True)

    valid = [a for a in actions if a.command]
    n = len(valid)
    if n == 0 and (not pcmd0):
        return NextActionUserTurn(no_match=True)

    # 3) Multi + vague yes (incl. bare “yes” and “ok”)
    if n > 1 and _wants_yesish(t) and _only_digits_choice(t) is None and _ordinal_index(t) is None:
        return NextActionUserTurn(
            immediate_assistant=(
                "Which one should I run? Reply `1`, `2`, or `3` (or `first` / `second` / `third`)."
            ),
        )
    if n > 1 and _wants_proceed_ok(t) and _only_digits_choice(t) is None and _ordinal_index(t) is None:
        return NextActionUserTurn(
            immediate_assistant=(
                "Which one should I run? Reply `1`, `2`, or `3` (or `first` / `second` / `third`)."
            ),
        )

    # 4) Single + yes / ok
    if n == 1 and (
        _wants_yesish(t)
        or _wants_proceed_ok(t)
        or t.lower() in ("do it", "do that", "run it")
    ):
        a0 = valid[0]
        if is_injectable_command(a0.command):
            return NextActionUserTurn(
                reprocess_user_text=a0.command,
                clear_suggestions=True,
                ack_line=ack_line_for_injected_command(a0.command),
            )
        return _pending_for_unknown(a0.command)

    # 5) index selection
    idx: int | None = _only_digits_choice(t)
    if idx is None:
        idx = _ordinal_index(t)

    if idx is not None:
        if idx < 1 or idx > min(n, 4):
            return NextActionUserTurn(
                immediate_assistant=(
                    f"Pick a number from 1 to {min(n, 4)} that matches the last “Next steps” list."
                ),
            )
        a_hit = next((x for x in valid if int(x.index) == idx), None)
        if a_hit is None and 1 <= idx <= len(valid):
            a_hit = valid[idx - 1]
        if a_hit is None:
            return NextActionUserTurn(
                immediate_assistant=(
                    f"Pick a number from 1 to {min(n, 4)} that matches the last “Next steps” list."
                ),
            )
        cmd = a_hit.command
        if is_injectable_command(cmd):
            return NextActionUserTurn(
                reprocess_user_text=cmd,
                clear_suggestions=True,
                ack_line=ack_line_for_injected_command(cmd),
            )
        return _pending_for_unknown(cmd)

    ncu = _match_suggestion_by_natural_cue(t, valid) if n >= 1 else None
    if ncu is not None and is_injectable_command(ncu.command):
        return NextActionUserTurn(
            reprocess_user_text=ncu.command,
            clear_suggestions=True,
            ack_line=ack_line_for_injected_command(ncu.command),
        )
    if ncu is not None and not is_injectable_command(ncu.command):
        return _pending_for_unknown(ncu.command)

    return NextActionUserTurn(no_match=True)


def _parse_pending_command(pending_json: str | None) -> str | None:
    if not (pending_json or "").strip():
        return None
    try:
        o = json.loads(pending_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not isinstance(o, dict):
        return None
    c = str(o.get("command") or "").strip()
    return c or None


def is_pending_inject_expired(pending_json: str | None) -> bool:
    if not (pending_json or "").strip():
        return False
    try:
        o = json.loads(pending_json)
    except (json.JSONDecodeError, TypeError, ValueError):
        return True
    if not isinstance(o, dict):
        return True
    ts0 = str(o.get("created_at") or "")
    if not ts0:
        return False
    now = datetime.now(timezone.utc)
    try:
        t = datetime.fromisoformat(ts0.replace("Z", "+00:00"))
    except ValueError:
        return True
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (now - t).total_seconds() > SUGGESTED_TTL_SECONDS


def _pending_for_unknown(cmd: str) -> NextActionUserTurn:
    """Ask once; we store command until user types `run` or re-picks something else that clears."""
    c = (cmd or "").strip()
    if not c:
        return NextActionUserTurn(no_match=True)
    short = c[:500] + ("…" if len(c) > 500 else "")
    return NextActionUserTurn(
        store_pending_command=c,
        clear_suggestions=False,  # keep list until they run; pending stored separately
        immediate_assistant=(
            f"I can use this as your next message in chat (same as if you typed it yourself):\n\n`{short}`\n\n"
            f"Reply `run` once to send it, or copy the line and paste it."
        ),
    )

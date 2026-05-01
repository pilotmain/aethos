import re

# Longer prefixes first so /improve wins over /in if that were ever an issue, etc.
DEV_PREFIXES = ("/improve", "/refactor", "/dev", "/fix", "/build")

CURSOR_REQUEST_PATTERNS = (
    # "to" is optional: users often write "ask cursor what should we build" not "ask cursor to …"
    # "cursor" / "dev agent" here are natural-language aliases for the Dev Agent, not a forced IDE.
    r"^(?:please\s+)?tell\s+cursor(?:\s+to)?\s+(.+)$",
    r"^(?:please\s+)?ask\s+cursor(?:\s+to)?\s+(.+)$",
    r"^(?:please\s+)?tell\s+dev(?:\s+agent)?(?:\s+to)?\s+(.+)$",
    r"^(?:please\s+)?ask\s+dev(?:\s+agent)?(?:\s+to)?\s+(.+)$",
    r"^(?:please\s+)?have\s+cursor\s+(.+)$",
    r"^(?:please\s+)?make\s+(?:a\s+)?cursor\s+task(?:\s+for)?\s+(.+)$",
    r"^(?:please\s+)?create\s+(?:a\s+)?cursor\s+task(?:\s+for)?\s+(.+)$",
    r"^(?:please\s+)?queue\s+(?:a\s+)?cursor\s+task(?:\s+for)?\s+(.+)$",
    r"^cursor[:,]?\s+(.+)$",
)

_LEADING_WORK_VERBS = (
    "work on ",
    "fix ",
    "build ",
    "refactor ",
    "improve ",
    "implement ",
    "handle ",
)

_AMBIGUOUS_REQUESTS = {
    "this",
    "that",
    "it",
    "this one",
    "that one",
    "work on this",
    "work on that",
    "fix this",
    "fix that",
    "build this",
    "build that",
    "refactor this",
    "refactor that",
    "improve this",
    "improve that",
}


def _dev_prefix_stripped(t: str) -> str | None:
    """If t looks like a dev task command, return the matched prefix, else None."""
    t = t.strip()
    low = t.lower()
    for p in sorted(DEV_PREFIXES, key=len, reverse=True):
        if low == p or low.startswith(p + " ") or low.startswith(p + "\n"):
            return p
    return None


def is_dev_task_message(text: str) -> bool:
    return _dev_prefix_stripped(text) is not None


def extract_cursor_request(text: str) -> str | None:
    stripped = (text or "").strip()
    if not stripped:
        return None

    for pattern in CURSOR_REQUEST_PATTERNS:
        match = re.match(pattern, stripped, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        payload = re.sub(r"\s+", " ", match.group(1).strip())
        if not payload:
            return None
        return payload
    return None


def is_cursor_request(text: str) -> bool:
    return extract_cursor_request(text) is not None


def build_cursor_instruction(text: str, replied_text: str | None = None) -> tuple[str, bool]:
    payload = extract_cursor_request(text)
    if payload is None:
        return "", False

    normalized = payload.strip().lower()
    if normalized in _AMBIGUOUS_REQUESTS and replied_text and replied_text.strip():
        return f"{payload}\n\nContext from replied message:\n{replied_text.strip()}", False

    if normalized in _AMBIGUOUS_REQUESTS:
        return payload, True

    for prefix in _LEADING_WORK_VERBS:
        if normalized.startswith(prefix):
            payload = payload[len(prefix) :].strip()
            break

    payload = payload.strip()
    if not payload:
        return "", True
    return payload, False


def parse_dev_task(text: str) -> tuple[str, str]:
    t = text.strip()
    p = _dev_prefix_stripped(t)
    if not p:
        return "Untitled dev task", t

    low = t.lower()
    if low == p:
        cleaned = ""
    else:
        cleaned = t[len(p) :].lstrip()

    if not cleaned.strip():
        return "Untitled dev task", "Untitled dev task"

    title = cleaned.split("\n", 1)[0].strip()
    title = re.sub(r"\s+", " ", title)
    if not title:
        title = "Untitled dev task"
    desc = cleaned.strip()
    return title[:120], desc

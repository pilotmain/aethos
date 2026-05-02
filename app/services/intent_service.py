import re

INTENTS = [
    "brain_dump",
    "capability_question",
    "help_request",
    "followup_reply",
    "stuck",
    "stuck_dev",
    "analysis",
    "status_update",
    "correction",
    "general_chat",
    "dev_command",
]

LEADING_FILLER_PATTERNS = [
    r"^\s*i need to\s+",
    r"^\s*i have to\s+",
    r"^\s*need to\s+",
    r"^\s*have to\s+",
    r"^\s*ugh\s+",
    r"^\s*maybe\s+",
    r"^\s*may be\s+",
    r"^\s*idk\s+",
    r"^\s*i should\s+",
    r"^\s*gotta\s+",
]

BAD_PHRASES = [
    "i feel overwhelmed",
    "i feel stressed",
    "i am overwhelmed",
    "i'm overwhelmed",
    "i have so much to do",
    "i have so much todo",
    "so much todo",
    "so much to do",
]

_SINGLE_WORD_OK = {"taxes", "groceries", "laundry", "email", "emails", "gym"}


def detect_intent(text: str) -> str:
    """Classify user intent; delegates to the LLM router with conservative fallbacks."""
    from app.services.intent_classifier import get_intent

    return get_intent(text)


def normalize_task(text: str) -> str:
    if not text:
        return ""

    t = text.lower().strip()

    for phrase in BAD_PHRASES:
        t = t.replace(phrase, " ")

    t = re.sub(r"[^\w\s]", " ", t)

    t = re.sub(r"\s+", " ", t).strip()

    changed = True
    while changed:
        changed = False
        for pattern in LEADING_FILLER_PATTERNS:
            new_t = re.sub(pattern, "", t)
            if new_t != t:
                t = new_t.strip()
                changed = True

    t = re.sub(r"^call to ", "call ", t)
    t = re.sub(r"^go to gym$", "go to the gym", t)
    t = re.sub(r"^gym tomorrow$", "go to the gym tomorrow", t)
    t = re.sub(r"^dentists$", "call the dentist", t)

    if t in {"help", "can you help", "please help", "todo", "to do"}:
        return ""

    words = t.split()
    if len(words) == 1 and t not in _SINGLE_WORD_OK:
        return ""

    if not t:
        return ""

    return t[:1].upper() + t[1:]


def is_valid_task(task_title: str) -> bool:
    if not task_title:
        return False

    lower = task_title.lower().strip()
    bad_exact = {
        "i have so much",
        "i have so much todo",
        "may be",
        "maybe",
        "help",
    }
    if lower in bad_exact:
        return False

    if len(lower.split()) == 0:
        return False

    return True


def preprocess_for_fallback(text: str) -> str:
    t = text.lower()
    t = re.sub(r"\bi feel\b.*", "", t)
    t = re.sub(r"\bi am stressed\b.*", "", t)
    t = re.sub(r"\bi'm stressed\b.*", "", t)
    t = t.replace("...", ",")
    t = t.replace(" and ", ",")
    t = t.replace(";", ",")
    return t.strip()


def handle_help() -> str:
    return (
        "Yes. Send me everything on your mind, "
        "and I'll reduce it to your next 1–3 steps."
    )


def handle_followup(last_task: str) -> str:
    return (
        f"No problem. Let's make it easier.\n\n"
        f"Next step: start with just 5 minutes of '{last_task}'."
    )


def handle_general() -> str:
    return (
        "Tell me what's on your mind, and I'll help you turn it into a simple plan."
    )

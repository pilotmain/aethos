"""
Low-level calls to external LLM providers (Anthropic / OpenAI).

Feature and routing code should not call these directly for user- or file-derived payloads.
Use :func:`app.services.safe_llm_gateway.safe_llm_json_call` and
:func:`app.services.safe_llm_gateway.safe_llm_text_call` unless the string is
already proven non-sensitive and internal-only (e.g. fixed system templates with no PII).
"""

import json
import logging
import re
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.services.intent_service import is_valid_task, normalize_task, preprocess_for_fallback
from app.services.llm_action_types import PLAN_REFINEMENT
from app.services.llm_key_resolution import MergedLlmKeyInfo, get_merged_api_keys
from app.services.llm_usage_context import push_llm_action
from app.services.llm_usage_recorder import (
    record_anthropic_message_usage,
    record_openai_message_usage,
)
from app.services.network_policy.policy import assert_provider_egress_allowed
from app.services.providers.sdk import build_anthropic_client, build_openai_client

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are an assistant that extracts clean, actionable tasks.

Rules:
- Do NOT repeat the user's phrasing
- Remove emotional language
- Convert to short verb-first tasks
- Max 6 tasks
- Detect emotional state (overwhelmed or normal)

Return JSON only:
{{
  "tasks": [
    {{
      "title": "",
      "priority": <number 1-100>
    }}
  ],
  "detected_state": "overwhelmed | normal"
}}

User input: {input}
"""

PLAN_PROMPT = """You help overwhelmed people decide what to do next.

Rules:
- Max 3 tasks if overwhelmed
- Keep tone calm and supportive
- Do NOT repeat full user text
- Do NOT list everything
- Focus on what matters most

Return JSON only (no markdown):
{{
  "summary": "",
  "tasks": [
    {{"title": "", "reason": ""}}
  ]
}}

Keep the same task order and count as below. Match each reason to the task at that position (1-based order).

Tasks:
{tasks}

State: {state}
"""

MICROSTEP_PROMPT = """Break this task into the smallest possible first step.

Rules:
- One action only
- Takes less than 5 minutes
- No explanation

Task: {task}

Return one line only, like: Open the document and write the first sentence"""


def _parse_json_object_from_llm(text: str) -> dict:
    raw = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    return json.loads(raw)


def _intent_classify_with_openai(
    user_prompt: str, openai_key: str, *, m: MergedLlmKeyInfo
) -> dict:
    s = get_settings()
    oai = build_openai_client(api_key=openai_key)
    logger.warning("INTENT_LLM_CALL_TRIGGERED provider=openai")
    response = oai.chat.completions.create(
        model=s.openai_model,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    try:
        record_openai_message_usage(
            response,
            model=s.openai_model,
            used_user_key=m.has_user_openai,
        )
    except Exception:  # noqa: BLE001
        pass
    out = response.choices[0].message.content or "{}"
    try:
        return _parse_json_object_from_llm(out)
    except (json.JSONDecodeError, TypeError) as e:
        logger.error("INTENT_LLM JSON_PARSE_FAILED raw=%s", out[:200])
        raise


def call_primary_llm_json(user_prompt: str) -> dict:
    """
    Call the primary configured LLM with a full user prompt; return a parsed JSON object.
    Tries Anthropic first, then OpenAI on Anthropic failure (matches response composer).
    Merges per-user (BYOK) keys with system env (see :func:`get_merged_api_keys`).
    """
    settings = get_settings()
    m = get_merged_api_keys()
    if not (m.anthropic_api_key or m.openai_api_key):
        raise RuntimeError("No LLM client configured for JSON call")

    if m.anthropic_api_key:
        try:
            logger.warning("INTENT_LLM_CALL_TRIGGERED provider=anthropic")
            client = build_anthropic_client(api_key=m.anthropic_api_key)
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1024,
                temperature=0.1,
                messages=[{"role": "user", "content": user_prompt}],
            )
            try:
                record_anthropic_message_usage(
                    msg,
                    model=settings.anthropic_model,
                    used_user_key=m.has_user_anthropic,
                )
            except Exception:  # noqa: BLE001
                pass
            body_parts: list[str] = []
            for block in msg.content:
                t = getattr(block, "text", None)
                if t:
                    body_parts.append(t)
            body = "".join(body_parts) if body_parts else "{}"
            return _parse_json_object_from_llm(body)
        except (json.JSONDecodeError, TypeError) as e:
            logger.error("INTENT_LLM JSON_PARSE_FAILED raw=%s", body[:200])
            if can_openai:
                logger.warning("INTENT_LLM anthropic body not JSON, trying openai: %s", e)
                try:
                    return _intent_classify_with_openai(user_prompt, m.openai_api_key, m=m)
                except Exception:
                    logger.exception("LLM_FAILURE call_primary_llm_json (openai after bad JSON)")
                    raise
            raise
        except Exception as e:
            if can_openai:
                logger.warning("INTENT_LLM anthropic failed, openai fallback: %s", e)
                try:
                    return _intent_classify_with_openai(user_prompt, m.openai_api_key, m=m)
                except Exception:
                    logger.exception("LLM_FAILURE call_primary_llm_json (openai fallback)")
                    raise
            logger.exception("LLM_FAILURE call_primary_llm_json")
            raise

    if can_openai:
        try:
            return _intent_classify_with_openai(user_prompt, m.openai_api_key, m=m)
        except Exception:
            logger.exception("LLM_FAILURE call_primary_llm_json")
            raise
    raise RuntimeError("No LLM client configured for JSON call")


def _text_from_anthropic_message(msg: object) -> str:
    body_parts: list[str] = []
    for block in msg.content:
        t = getattr(block, "text", None)
        if t:
            body_parts.append(t)
    return "".join(body_parts) if body_parts else ""


def call_primary_llm_text(user_prompt: str) -> str:
    """
    Call the primary configured LLM; return raw combined text (no JSON parse).
    Same provider order as :func:`call_primary_llm_json` (Anthropic, then OpenAI).
    """
    settings = get_settings()
    m = get_merged_api_keys()
    if not (m.anthropic_api_key or m.openai_api_key):
        raise RuntimeError("No LLM client configured for text call")

    can_anthropic = bool(m.anthropic_api_key) and assert_provider_egress_allowed("anthropic", None) is None
    can_openai = bool(m.openai_api_key) and assert_provider_egress_allowed("openai", None) is None
    if not can_anthropic and not can_openai:
        raise RuntimeError("LLM outbound blocked by network egress policy (or no provider keys)")

    if can_anthropic:
        try:
            logger.warning("LLM_TEXT_CALL_TRIGGERED provider=anthropic")
            client = build_anthropic_client(api_key=m.anthropic_api_key)
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                temperature=0.3,
                messages=[{"role": "user", "content": user_prompt}],
            )
            try:
                record_anthropic_message_usage(
                    msg,
                    model=settings.anthropic_model,
                    used_user_key=m.has_user_anthropic,
                )
            except Exception:  # noqa: BLE001
                pass
            return _text_from_anthropic_message(msg)
        except Exception as e:
            if not can_openai:
                logger.exception("LLM_FAILURE call_primary_llm_text (anthropic)")
                raise
            logger.warning("LLM_TEXT anthropic failed, openai fallback: %s", e)

    if can_openai:
        oai = build_openai_client(api_key=m.openai_api_key)
        logger.warning("LLM_TEXT_CALL_TRIGGERED provider=openai")
        response = oai.chat.completions.create(
            model=settings.openai_model,
            temperature=0.3,
            messages=[{"role": "user", "content": user_prompt}],
        )
        try:
            record_openai_message_usage(
                response,
                model=settings.openai_model,
                used_user_key=m.has_user_openai,
            )
        except Exception:  # noqa: BLE001
            pass
        return (response.choices[0].message.content or "").strip()

    raise RuntimeError("No LLM client configured for text call")


def _infer_category_from_title(title: str) -> str:
    lower = title.lower()
    if any(k in lower for k in ["report", "email", "meeting", "client", "deck"]):
        return "work"
    if any(k in lower for k in ["gym", "walk", "doctor", "sleep"]):
        return "health"
    if any(k in lower for k in ["mom", "dad", "friend", "partner", "family"]):
        return "personal"
    if any(k in lower for k in ["book", "pay", "renew", "flight", "call", "appointment"]):
        return "admin"
    return "general"


def _normalize_extraction_payload(data: dict, now: datetime) -> dict:
    raw_state = str(data.get("detected_state") or "normal").lower().strip()
    if raw_state == "overwhelmed":
        detected_state = "overwhelm"
    elif raw_state == "overwhelm":
        detected_state = "overwhelm"
    elif raw_state == "normal":
        detected_state = "normal"
    else:
        detected_state = "normal"

    tasks_out: list[dict] = []
    for item in (data.get("tasks") or [])[:6]:
        title = str(item.get("title") or "").strip()
        title = normalize_task(title)
        if not title or not is_valid_task(title):
            continue
        pri_raw = item.get("priority")
        try:
            priority_score = max(1, min(int(pri_raw), 100))
        except (TypeError, ValueError):
            priority_score = 55
        cat = item.get("category") or _infer_category_from_title(title)
        suggested_for_date = None
        lower = title.lower()
        if "tomorrow" in lower:
            suggested_for_date = (now.date() + timedelta(days=1)).isoformat()
        elif "today" in lower:
            suggested_for_date = now.date().isoformat()
        tasks_out.append(
            {
                "title": title[:255],
                "description": None,
                "category": cat if isinstance(cat, str) else "general",
                "priority_score": priority_score,
                "due_at": None,
                "suggested_for_date": suggested_for_date,
            }
        )

    return {"detected_state": detected_state, "tasks": tasks_out}


class LLMService:
    def __init__(self) -> None:
        self.settings = get_settings()
        s = self.settings
        self.client = (
            build_anthropic_client(api_key=s.anthropic_api_key) if s.anthropic_api_key else None
        )
        self.openai_client = build_openai_client(api_key=s.openai_api_key) if s.openai_api_key else None

    def _clients_from_merge(self) -> tuple[object | None, object | None]:
        """For requests that can use BYOK, prefer :func:`get_merged_api_keys` over self.*."""
        m = get_merged_api_keys()
        acli = ocli = None
        if m.anthropic_api_key:
            acli = build_anthropic_client(api_key=m.anthropic_api_key)
        if m.openai_api_key:
            ocli = build_openai_client(api_key=m.openai_api_key)
        if acli or ocli:
            return (acli, ocli)
        return (self.client, self.openai_client)

    def detect_state(self, text: str) -> str:
        lowered = text.lower()
        overload_terms = [
            "overwhelmed",
            "stressed",
            "too much",
            "can't keep up",
            "chaos",
            "anxious",
            "behind",
        ]
        return "overwhelm" if any(term in lowered for term in overload_terms) else "normal"

    def extract_tasks(self, text: str, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC).replace(tzinfo=None)
        if not self.settings.use_real_llm:
            return self._extract_tasks_local(text, now=now)

        anth_c, oai_c = self._clients_from_merge()
        if anth_c:
            try:
                payload = self._extract_tasks_anthropic_with_client(
                    text, now, anth_c
                )
                normalized = _normalize_extraction_payload(payload, now)
                if normalized["tasks"]:
                    return normalized
            except Exception:
                pass

        if oai_c:
            try:
                payload = self._extract_tasks_openai_with_client(text, now, oai_c)
                normalized = _normalize_extraction_payload(payload, now)
                if normalized["tasks"]:
                    return normalized
            except Exception:
                pass

        return self._extract_tasks_local(text, now=now)

    def _extract_tasks_openai_with_client(self, text: str, now: datetime, oai) -> dict:
        m = get_merged_api_keys()
        with push_llm_action(action_type=PLAN_REFINEMENT, agent_key="nexa"):
            prompt = EXTRACTION_PROMPT.format(input=text)
            response = oai.chat.completions.create(
                model=self.settings.openai_model,
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            try:
                record_openai_message_usage(
                    response,
                    model=self.settings.openai_model,
                    used_user_key=m.has_user_openai,
                )
            except Exception:  # noqa: BLE001
                pass
            body = response.choices[0].message.content or "{}"
        return _parse_json_object_from_llm(body)

    def _extract_tasks_anthropic_with_client(self, text: str, now: datetime, client) -> dict:  # noqa: ARG002
        m = get_merged_api_keys()
        with push_llm_action(action_type=PLAN_REFINEMENT, agent_key="nexa"):
            prompt = EXTRACTION_PROMPT.format(input=text)
            message = client.messages.create(
                model=self.settings.anthropic_model,
                max_tokens=4096,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}],
            )
            try:
                record_anthropic_message_usage(
                    message,
                    model=self.settings.anthropic_model,
                    used_user_key=m.has_user_anthropic,
                )
            except Exception:  # noqa: BLE001
                pass
            parts: list[str] = []
            for block in message.content:
                block_text = getattr(block, "text", None)
                if block_text:
                    parts.append(block_text)
            body = "".join(parts) if parts else "{}"
        return _parse_json_object_from_llm(body)

    def refine_plan_language(self, task_titles: list[str], detected_state: str) -> dict | None:
        """Returns {summary: str, reasons: list[str]} aligned with task_titles, or None."""
        if not task_titles:
            return None
        lines = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(task_titles))
        prompt = PLAN_PROMPT.format(tasks=lines, state=detected_state)

        body: str | None = None
        anth_c, oai_c = self._clients_from_merge()
        m = get_merged_api_keys()
        with push_llm_action(action_type=PLAN_REFINEMENT, agent_key="nexa"):
            if anth_c:
                try:
                    message = anth_c.messages.create(
                        model=self.settings.anthropic_model,
                        max_tokens=2048,
                        temperature=0.3,
                        messages=[{"role": "user", "content": prompt}],
                    )
                    try:
                        record_anthropic_message_usage(
                            message,
                            model=self.settings.anthropic_model,
                            used_user_key=m.has_user_anthropic,
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    body_parts: list[str] = []
                    for block in message.content:
                        bt = getattr(block, "text", None)
                        if bt:
                            body_parts.append(bt)
                    body = "".join(body_parts) if body_parts else "{}"
                except Exception:
                    body = None

            if body is None and oai_c:
                try:
                    response = oai_c.chat.completions.create(
                        model=self.settings.openai_model,
                        temperature=0.3,
                        response_format={"type": "json_object"},
                        messages=[{"role": "user", "content": prompt}],
                    )
                    try:
                        record_openai_message_usage(
                            response,
                            model=self.settings.openai_model,
                            used_user_key=m.has_user_openai,
                        )
                    except Exception:  # noqa: BLE001
                        pass
                    body = response.choices[0].message.content or "{}"
                except Exception:
                    return None

        if body is None:
            return None

        try:
            data = _parse_json_object_from_llm(body)
        except Exception:
            return None

        summary = str(data.get("summary") or "").strip()
        raw_tasks = data.get("tasks") or []
        reasons: list[str] = []
        for i in range(len(task_titles)):
            reason = ""
            if i < len(raw_tasks) and isinstance(raw_tasks[i], dict):
                reason = str(raw_tasks[i].get("reason") or "").strip()
            reasons.append(reason)
        if not summary:
            return None
        return {"summary": summary, "reasons": reasons}

    def _extract_tasks_local(self, text: str, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC).replace(tzinfo=None)
        pre = preprocess_for_fallback(text)
        stripped = re.sub(r"[.,]?\s*i feel\b.*$", "", pre, flags=re.IGNORECASE).strip()
        normalized = stripped.replace("\n", ", ")
        parts = [p.strip(" .") for p in re.split(r",| and |;", normalized) if p.strip(" .")]
        tasks = []
        for part in parts:
            nt = normalize_task(part)
            if not nt or not is_valid_task(nt):
                continue
            lower = nt.lower()
            category = "general"
            if any(k in lower for k in ["report", "email", "meeting", "client", "deck"]):
                category = "work"
            elif any(k in lower for k in ["gym", "walk", "doctor", "sleep"]):
                category = "health"
            elif any(k in lower for k in ["mom", "dad", "friend", "partner", "family"]):
                category = "personal"
            elif any(k in lower for k in ["book", "pay", "renew", "flight", "call", "appointment"]):
                category = "admin"
            priority = 55
            if any(k in lower for k in ["urgent", "asap", "today", "finish", "deadline"]):
                priority += 25
            if any(k in lower for k in ["tomorrow", "later"]):
                priority -= 5
            due_at = None
            suggested_for_date = None
            if "tomorrow" in lower:
                suggested_for_date = (now.date() + timedelta(days=1)).isoformat()
            elif "today" in lower:
                suggested_for_date = now.date().isoformat()
            tasks.append(
                {
                    "title": nt[:255],
                    "description": None,
                    "category": category,
                    "priority_score": max(1, min(priority, 100)),
                    "due_at": due_at,
                    "suggested_for_date": suggested_for_date,
                }
            )
        if not tasks:
            nt = normalize_task(text)
            if nt and is_valid_task(nt):
                tasks = [{
                    "title": nt[:255],
                    "description": None,
                    "category": "general",
                    "priority_score": 50,
                    "due_at": None,
                    "suggested_for_date": now.date().isoformat(),
                }]
        return {"detected_state": self.detect_state(text), "tasks": tasks}

    def generate_followup(self, task_title: str, planning_style: str = "gentle") -> str:
        if planning_style == "direct":
            return f"Quick check: did you finish '{task_title}' or should we replan it?"
        return f"Quick check-in: did you make progress on '{task_title}', or should we shrink it into a smaller step?"

    def generate_micro_step(self, task_title: str, planning_style: str = "gentle") -> str:
        if planning_style == "direct":
            return f"Next step: spend 10 minutes on '{task_title}'."
        return f"Let's reduce the pressure: take one tiny step on '{task_title}' for just 10 minutes."

"""Vision completion chain (Phase 18b) — routes multimodal :class:`Message` turns to providers."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.services.llm.base import Message
from app.services.llm.bootstrap import register_llm_providers_from_settings
from app.services.llm.content_parts import image_data_url
from app.services.llm.providers.anthropic_backend import AnthropicBackend
from app.services.llm.providers.gemini_backend import GeminiBackend
from app.services.llm.providers.ollama_backend import OllamaBackend
from app.services.llm.providers.openai_backend import OpenAIBackend
from app.services.llm.registry import get_llm_registry
from app.services.llm_key_resolution import get_merged_api_keys
from app.services.network_policy.policy import assert_provider_egress_allowed

logger = logging.getLogger(__name__)

_VISION_DEFAULTS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-1.5-flash",
    "ollama": "llava:latest",
}

_AUTO_ORDER = ("openai", "anthropic", "gemini", "ollama")


def _resolve_api_key(provider: str, s: Settings) -> str | None:
    m = get_merged_api_keys()
    if provider == "openai":
        return (m.openai_api_key or s.openai_api_key or s.nexa_llm_api_key or "").strip() or None
    if provider == "anthropic":
        return (m.anthropic_api_key or s.anthropic_api_key or "").strip() or None
    if provider == "gemini":
        return (s.nexa_gemini_api_key or "").strip() or None
    if provider == "ollama":
        return "local"  # no key
    return None


def _vision_model_for(provider: str, s: Settings) -> str:
    override = (s.nexa_multimodal_vision_model or "").strip()
    if override:
        return override
    if provider == "ollama":
        return (s.nexa_ollama_default_model or _VISION_DEFAULTS["ollama"]).strip()
    return _VISION_DEFAULTS.get(provider, "")


def _clone_provider_for_vision(name: str, settings: Settings) -> Any | None:
    register_llm_providers_from_settings()
    reg = get_llm_registry()
    prov = reg.get_provider(name)
    if not prov:
        return None
    model = _vision_model_for(name, settings)
    if name == "openai" and isinstance(prov, OpenAIBackend):
        return OpenAIBackend(
            logical_name=prov.logical_name,
            api_key=prov._api_key,  # noqa: SLF001
            model=model,
            base_url=prov._base_url,  # noqa: SLF001
            timeout=prov._timeout,  # noqa: SLF001
            usage_provider=prov._usage_provider,  # noqa: SLF001
            used_user_key=prov._used_user_key,  # noqa: SLF001
        )
    if name == "anthropic" and isinstance(prov, AnthropicBackend):
        return prov.clone_with_model(model)
    if name == "ollama" and isinstance(prov, OllamaBackend):
        root = str(getattr(prov, "_root", "") or "").strip().rstrip("/")
        if not root.startswith("http"):
            root = (settings.nexa_ollama_base_url or "http://127.0.0.1:11434").strip().rstrip("/")
        return OllamaBackend(
            base_url=root,
            model=model,
            timeout=float(getattr(prov, "_timeout", 120.0)),
        )

    return None


def _build_gemini_backend(s: Settings) -> GeminiBackend | None:
    key = (s.nexa_gemini_api_key or "").strip()
    if not key:
        return None
    return GeminiBackend(api_key=key, model=_vision_model_for("gemini", s), timeout=float(s.nexa_provider_timeout_seconds or 120.0))


def vision_complete_chat(messages: list[Message]) -> tuple[str, dict[str, Any]]:
    """
    Run a vision-capable completion. Returns ``(assistant_text, meta)`` where meta includes
    ``provider`` and ``model`` used.
    """
    s = get_settings()
    choice = (s.nexa_multimodal_vision_provider or "auto").strip().lower()
    order: tuple[str, ...]
    if choice in ("", "auto"):
        order = _AUTO_ORDER
    else:
        order = (choice,)

    last_err: Exception | None = None
    for name in order:
        if name not in _AUTO_ORDER:
            logger.warning("unknown vision provider %s", name)
            continue
        if name == "gemini":
            gem = _build_gemini_backend(s)
            if not gem:
                continue
            block = assert_provider_egress_allowed("google", None)
            if block:
                logger.warning("vision gemini blocked: %s", block)
                continue
            try:
                text = gem.complete_chat(messages, temperature=float(s.nexa_llm_temperature), max_tokens=s.nexa_llm_max_tokens)
                return text, {"provider": "gemini", "model": gem._model}  # noqa: SLF001
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                logger.warning("vision gemini failed: %s", exc)
            continue

        key = _resolve_api_key(name, s)
        if not key and name != "ollama":
            continue

        prov = _clone_provider_for_vision(name, s)
        if not prov:
            continue
        block = assert_provider_egress_allowed(name, None)
        if block:
            logger.warning("vision %s blocked by egress: %s", name, block)
            continue
        try:
            text = prov.complete_chat(
                messages,
                temperature=float(s.nexa_llm_temperature),
                max_tokens=s.nexa_llm_max_tokens,
            )
            mid = getattr(prov, "_model", None) or _vision_model_for(name, s)
            return text, {"provider": name, "model": mid}
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("vision provider %s failed: %s", name, exc)

    if last_err is not None:
        raise last_err
    raise RuntimeError(
        "No vision provider available (configure API keys / Ollama / NEXA_GEMINI_API_KEY, or check egress allowlist)."
    )


async def fetch_url_to_data_url(url: str, *, max_bytes: int) -> str:
    """Fetch an http(s) image and return a data URL suitable for vision models."""
    u = (url or "").strip()
    if u.startswith("data:"):
        return u
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(u)
        r.raise_for_status()
        body = r.content
        if len(body) > max_bytes:
            raise ValueError("image exceeds max_bytes")
        ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
        if not ct.startswith("image/"):
            raise ValueError("URL did not return an image content-type")
        return image_data_url(ct, body)


def normalize_messages_with_remote_images(messages: list[Message], *, max_bytes: int) -> list[Message]:
    """Resolve ``https://`` image URLs inside OpenAI-style blocks to data URLs (async callers should use fetch)."""
    # Sync variant for tests — uses httpx sync client
    out: list[Message] = []
    for m in messages:
        if m.role != "user" or isinstance(m.content, str):
            out.append(m)
            continue
        new_blocks: list[dict[str, Any]] = []
        changed = False
        for b in m.content:
            if not isinstance(b, dict) or b.get("type") != "image_url":
                new_blocks.append(b)
                continue
            iu = b.get("image_url") or {}
            url = str((iu.get("url") if isinstance(iu, dict) else "") or "").strip()
            if url.startswith("http://") or url.startswith("https://"):
                with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                    r = client.get(url)
                    r.raise_for_status()
                    raw = r.content
                    if len(raw) > max_bytes:
                        raise ValueError("image exceeds max_bytes")
                    ct = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
                    if not ct.startswith("image/"):
                        raise ValueError("URL did not return an image content-type")
                    data_url = image_data_url(ct, raw)
                    detail = iu.get("detail") if isinstance(iu, dict) else None
                    nb: dict[str, Any] = {"type": "image_url", "image_url": {"url": data_url}}
                    if detail:
                        nb["image_url"]["detail"] = detail
                    new_blocks.append(nb)
                    changed = True
            else:
                new_blocks.append(b)
        if changed:
            out.append(Message(role=m.role, content=new_blocks, name=m.name, tool_calls=m.tool_calls, tool_call_id=m.tool_call_id))
        else:
            out.append(m)
    return out

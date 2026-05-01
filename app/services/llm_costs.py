"""
Estimated USD cost from public model pricing (placeholders; provider dashboards are source of truth).
"""

from __future__ import annotations

import re

# USD per 1M tokens
PRICING_USD_PER_1M_TOKENS: dict[str, dict[str, dict[str, float]]] = {
    "anthropic": {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
        "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
        "claude-3-5-haiku-20241022": {"input": 0.8, "output": 4.0},
        "claude-3-7-sonnet": {"input": 3.0, "output": 15.0},
        # 4.5+ era — conservative placeholders; verify on Anthropic’s pricing page
        "claude-sonnet-4-5": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
    },
    "openai": {
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "gpt-4.1": {"input": 2.0, "output": 8.0},
        "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    },
}


def get_known_model_pricing() -> dict[str, dict[str, dict[str, float]]]:
    return PRICING_USD_PER_1M_TOKENS


def normalize_model_name(provider: str, model: str | None) -> str | None:
    if not model or not (model or "").strip():
        return None
    m = (model or "").strip()
    p = (provider or "").lower().strip()
    if p == "openai":
        m = re.sub(r"^openai/|^models/", "", m, flags=re.IGNORECASE)
    m = m.lower()
    for sub in (":", "@", "#"):
        if sub in m:
            m = m.split(sub, 1)[0]
    m = m.strip() or None
    return m


def estimate_llm_cost(
    provider: str, model: str | None, input_tokens: int, output_tokens: int
) -> float | None:
    p = (provider or "").lower().strip()
    nm = normalize_model_name(p, model)
    if not nm or p not in PRICING_USD_PER_1M_TOKENS:
        return None
    by_model = PRICING_USD_PER_1M_TOKENS.get(p) or {}
    if nm in by_model:
        row = by_model[nm]
    else:
        # Match longest known id prefix
        best: dict[str, float] | None = None
        best_len = 0
        for key, v in by_model.items():
            if nm.startswith(key) and len(key) > best_len:
                best, best_len = v, len(key)
        row = best
    if not row:
        return None
    ins = (input_tokens or 0) / 1_000_000.0 * float(row.get("input", 0.0))
    ous = (output_tokens or 0) / 1_000_000.0 * float(row.get("output", 0.0))
    return float(ins + ous)

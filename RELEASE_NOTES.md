# AethOS — Release notes (local-first LLM track)

This document summarizes the **local / Ollama-first** intent classification track, benchmark scope, and operator caveats. For full architecture, see `docs/DESIGN.md` (§2.3–§2.4, §4.3).

## Benchmark scope (intent axis)

- **Harness:** `tests/benchmark/run_benchmark.py` with golden cases in `tests/benchmark/prompts.json`.
- **Size:** **65** fixed **agent-task intent** cases (not open-ended chat).
- **Reference result:** **100%** label match using **`qwen2.5:7b`** via Ollama when the shared few-shot block in `app/services/intent_classifier_prompt_shots.py` is applied (same text is appended to production `INTENT_CLASSIFIER_SYSTEM` in `intent_classifier.py`).
- **Do not over-claim:** accuracy applies **only** to that suite; production NL is unconstrained.

## Default model (Ollama)

- **Settings default:** `nexa_ollama_default_model` → **`qwen2.5:7b`** (`app/core/config.py`).
- **Pull:** `ollama pull qwen2.5:7b` and ensure `GET /api/tags` lists the tag (`is_ollama_ready()` in `app/services/llm/bootstrap.py`).

## Configuration (local-only inference)

Pick **one** of these patterns so Ollama is registered and `providers_available()` can be true without cloud keys:

| Goal | Typical `.env` |
|------|------------------|
| Ollama as explicit primary | `NEXA_LLM_PROVIDER=ollama` and `NEXA_OLLAMA_ENABLED=true` |
| Auto chain + prefer local tooling flags | `NEXA_LLM_PROVIDER=auto` with `NEXA_LOCAL_FIRST=true` (registers Ollama when CLI path matches bootstrap) |
| Wizard install | `scripts/setup.py` may set `NEXA_OLLAMA_ENABLED=true` when `ollama` is on `PATH` |

Also set `USE_REAL_LLM=true` for LLM-backed intent when a provider is available.

**Cloud keys:** If **Anthropic / OpenAI / DeepSeek / OpenRouter** keys are present and `NEXA_LLM_PROVIDER=auto`, the Phase‑11 chain **still prefers cloud providers first** unless you pin `ollama` or remove cloud keys. For **strict local-only** behavior, configure primary provider and keys accordingly.

## Caveats

1. **Ollama down or empty `/api/tags`:** `providers_available()` is false → intent uses **`classify_intent_fallback`** heuristics; replies use template / fallback composition paths until Ollama recovers (~15s readiness cache TTL).
2. **Intent fast paths:** `get_intent` still applies deterministic gates (e.g. greeting, config query) before the LLM; latency profiles must state whether they measure **`classify_intent_llm`** only or end-to-end `get_intent`.
3. **RAM:** Python process RSS does not include the **Ollama server** or loaded GGUF weights; capture **Ollama** PID RSS separately (see `scripts/benchmark_performance.py`).

## Performance artifacts

Run locally and attach JSON + console summary to a release:

```bash
python scripts/benchmark_performance.py --runs 100 --json-out data/benchmark_performance/latest.json
```

## Pure local LLM mode (`NEXA_PURE_LOCAL_LLM_MODE`)

When set to **`true`** and at least one LLM provider is reachable (`providers_available()`):

- **Intent:** skips regex fast-paths; uses **`classify_intent_llm`** (same few-shots as the benchmark). If nothing is reachable, uses **`classify_intent_fallback`** only.
- **Completion chain:** **Ollama** is tried **first** when registered (then existing cloud order).
- **Composer:** skips the canned research-capability block for capability questions; replies go through the LLM. If no provider is up, users get a short **offline** notice instead of the full template fallback tree.

Default is **`false`** so CI and installs without Ollama keep current hybrid behavior.

```bash
pytest tests/release_gate.py -q --tb=short
```

Optional skips: see docstrings in `tests/release_gate.py` (`SKIP_RELEASE_GATE_BENCHMARK`, etc.).

# Agent-task intent benchmark

Offline-curated prompts (`prompts.json`) score how well a **local Ollama** model (default **`phi3:mini`**) returns JSON aligned with golden **`intent`** labels. This is a **narrow axis** (intent classification style); it does **not** prove end-to-end host-executor or gateway safety — see `docs/DESIGN.md` **§2.4** (router vs model) and **§4.3** for scope and for **>95%** claims: define a fixed task suite and treat numbers as regression deltas, not “beats GPT-4 on chat”.

## Prerequisites

- [Ollama](https://ollama.com) running (`ollama serve` or the app service).
- Model pulled, e.g. `ollama pull phi3:mini` (must appear in `GET /api/tags`).

## Run

From the repo root (`.venv` active):

```bash
python tests/benchmark/run_benchmark.py \
  --base-url http://127.0.0.1:11434 \
  --json-out /tmp/benchmark-report.json \
  --markdown-out /tmp/benchmark-report.md
```

Optional: `--model other:tag` overrides `ollama_model` from `prompts.json`.

Exit code **0** only if **all** cases match (strict CI gate). For exploratory runs, ignore exit code and read the JSON/Markdown reports.

## Outputs

- **JSON** — per-case `expected_intent`, `predicted_intent`, `match`, latency, short `raw_reply_preview`, optional `error`.
- **Markdown** — summary table for humans.

## CI

Default `pytest` does **not** call Ollama. `tests/test_benchmark_smoke.py` validates `prompts.json` shape and JSON extraction helpers only.

## Extending

Add rows to `prompts.json` → `cases` (keep `expected.intent` in the `intents` allow-list). Re-run the script and track accuracy over time.

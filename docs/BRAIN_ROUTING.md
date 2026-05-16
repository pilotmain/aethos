# Brain routing (Phase 2 Step 7)

AethOS orchestrates repair workflows; **brains** (local Ollama, configured LLM providers, or deterministic fallback) produce structured repair plans. Execution, verification, and redeploy stay in AethOS tools.

## Selection order

1. Local model when `AETHOS_LOCAL_FIRST_ENABLED` / `NEXA_LOCAL_FIRST` and Ollama is available
2. Primary configured provider (`NEXA_LLM_PROVIDER` / API keys)
3. Fallback providers from the registry
4. `deterministic` when `USE_REAL_LLM=false`, `NEXA_PYTEST=1`, or no external brain is allowed

## Privacy

- Evidence is scanned before external calls (`repair_evidence`, `repair_brain`).
- `local_only` / `block` modes force local or deterministic brains.
- Redact mode may redact evidence sent externally.

## Repair API / CLI

- `POST /api/v1/projects/{id}/fix-and-redeploy`
- `GET /api/v1/projects/{id}/latest-repair` — includes `brain_decision`, `evidence_summary`, `verification_result`
- `aethos deploy fix-and-redeploy <project>`
- `aethos projects latest-repair <project>`

## Modules

- `app/brain/` — selection, registry, events, `repair_brain.py`
- `app/providers/repair/repair_evidence.py` — safe evidence bundle
- `app/providers/repair/repair_plan_validation.py` — validate brain JSON before execution
- `app/providers/repair/repair_safe_edits.py` — checkpointed in-repo edits

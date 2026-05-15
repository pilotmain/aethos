# Development contributing guide

AethOS development is currently governed by the OpenClaw parity-first rule.

## Rule

Reproduce OpenClaw behavior first. Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

## Required PR answers

```text
OpenClaw behavior reproduced:
Parity checkpoint advanced:
Verification performed:
Remaining divergence:
```

## Verification

```bash
python -m compileall -q app
pytest
pytest tests/test_openclaw_parity.py
```

## Deferred until after parity

- privacy-first redesigns
- PII filtering systems
- local-first-only behavior that changes parity semantics
- safety-layer redesigns
- custom orchestration experiments
- novel agent frameworks
- custom UX paradigms

See [../../PROJECT_HANDOFF.md](../../PROJECT_HANDOFF.md) and [../OPENCLAW_PARITY_AUDIT.md](../OPENCLAW_PARITY_AUDIT.md).

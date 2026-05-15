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
python -m compileall -q app aethos_cli
pytest
pytest tests/test_openclaw_parity.py
pytest tests/test_openclaw_*_parity.py
pytest tests/test_openclaw_runtime_*.py
pytest tests/test_openclaw_task_*.py tests/test_openclaw_scheduler.py tests/test_openclaw_queue_*.py tests/test_openclaw_agent_runtime.py tests/test_openclaw_orchestration_recovery.py tests/test_openclaw_deployment_recovery.py tests/test_openclaw_runtime_dispatcher.py
pytest tests/test_openclaw_execution_*.py tests/test_openclaw_autonomous_execution.py
pytest tests/test_openclaw_doctrine_docs.py
```

See [../OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](../OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md) for the master plan (CLI matrix, priorities, test modules).

## Deferred until after parity

- privacy-first redesigns
- PII filtering systems
- local-first-only behavior that changes parity semantics
- safety-layer redesigns
- custom orchestration experiments
- novel agent frameworks
- custom UX paradigms

See [../../PROJECT_HANDOFF.md](../../PROJECT_HANDOFF.md) and [../OPENCLAW_PARITY_AUDIT.md](../OPENCLAW_PARITY_AUDIT.md).

# Contributing

Thank you for contributing to AethOS.

## Current project objective

AethOS is in a strict **OpenClaw parity-first** phase.

The project goal is to reproduce OpenClaw exactly as it works today. Privacy, PII filtering, local-first differentiation, cost transparency, and custom AethOS-specific improvements are Phase 2 unless they are required to reproduce current OpenClaw behavior.

## Contribution rule

Every feature PR must answer:

1. Does this move us closer to OpenClaw parity?
2. What OpenClaw behavior does this reproduce?
3. Which parity checkpoint does it advance?
4. How was the behavior verified?
5. Does this introduce any architectural divergence?

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

## Code of conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Be respectful, constructive, and assume good intent.

## How to contribute

1. Fork the repository or use a branch if you have write access.
2. Create a focused feature branch.
3. Make the smallest change that advances OpenClaw parity.
4. Add or update tests where practical, especially parity coverage.
5. Run the verification commands below.
6. Open a Pull Request with a clear parity-focused description.

## Verification

Run before opening a PR:

```bash
python -m compileall -q app aethos_cli
pytest
pytest tests/test_openclaw_parity.py
pytest tests/test_openclaw_*_parity.py
pytest tests/test_openclaw_runtime_*.py
pytest tests/test_openclaw_task_*.py tests/test_openclaw_scheduler.py tests/test_openclaw_queue_*.py tests/test_openclaw_agent_runtime.py tests/test_openclaw_orchestration_recovery.py tests/test_openclaw_deployment_recovery.py tests/test_openclaw_runtime_dispatcher.py
pytest tests/test_openclaw_execution_*.py tests/test_openclaw_autonomous_execution.py
pytest tests/test_openclaw_doctrine_docs.py
pytest tests/test_openclaw_reliability_consistency.py tests/test_openclaw_continuity_consistency.py tests/test_openclaw_warning_consistency.py
pytest tests/production_like/ tests/edge_cases/ tests/soak/ tests/openclaw_behavioral_validation/
# Phase 1 gate helpers: tests/parity_freeze_gate.py (MIN_REPEATED_CYCLES=100; widen_runtime_event_buffer for high-volume lifecycle tests)
```

Optional style check:

```bash
ruff check app tests
```

## Phase 1 deferrals

Defer the following unless needed for exact OpenClaw behavior:

- privacy-first redesigns
- PII filtering systems
- safety-layer redesigns
- custom orchestration experiments
- novel agent frameworks
- custom UX paradigms
- cost/local-first features that change OpenClaw-compatible semantics

## Development setup

See [docs/development/setup.md](docs/development/setup.md).

## Style

- Match existing patterns for types, naming, logging, settings, and tests.
- Prefer behavior-preserving changes over broad rewrites.
- Keep `.env.example`, docs, and parity tests synchronized with code changes.

## License

By contributing, you agree your contributions are licensed under the Apache License 2.0. See [LICENSE](LICENSE).

## Getting help

- Open a [GitHub issue](https://github.com/pilotmain/aethos/issues).
- Commercial licensing: [license@aethos.ai](mailto:license@aethos.ai).

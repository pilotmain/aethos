# Legacy reference policy

Severity: `critical` · `operator_visible` · `internal_only` · `allowed`

## Allowed

- `NEXA_*` compatibility env aliases
- `docs/OPENCLAW_*` parity documentation
- `tests/test_openclaw_*`
- README inspiration line for OpenClaw

## Must replace (operator surfaces)

Mission Control UI, CLI help, setup wizard, recovery/restart copy, marketplace user strings.

Module: `app/services/setup/legacy_reference_policy.py`

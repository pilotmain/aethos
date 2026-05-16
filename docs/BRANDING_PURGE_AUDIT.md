# Branding purge audit (Phase 4 Step 11)

**User-facing brand:** AethOS

## Allowed

- README: *Inspired by OpenClaw.*
- `docs/OPENCLAW_*`, `tests/test_openclaw_*` (parity)
- `NEXA_*` in `.env.example`, config, compatibility paths
- Differentiators page (comparison context)

## Removed from user-facing CLI/UI (Step 11)

- OpenClaw / ClawHub / OpenHub in CLI help and common MC copy
- Marketplace copy uses “skill registry” instead of ClawHub

## Verify

```bash
aethos setup certify   # includes branding_audit.violation_count
pytest tests/test_branding_purge.py
```

Module: `app/services/setup/branding_purge.py`

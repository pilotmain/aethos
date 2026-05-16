# Enterprise operator trust (Phase 4 Step 12)

Module: `enterprise_operator_trust.py`

Operator-facing messages replace raw errors:

- Connection unavailable → recovery attempt messaging
- Degraded → needs attention + advisories
- Throttling → performance protection

API: `GET /api/v1/runtime/operator-experience`

Web: `web/lib/runtimeResilience.ts` formats HTTP errors for calm MC panels.

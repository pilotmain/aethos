# Operator error experience

Calm copy replaces raw technical failures:

- Connection: *AethOS runtime connection is not available yet…*
- 5xx panels: *AethOS runtime hit an internal error while loading this panel…*
- Unknown provider: *not available in the current AethOS runtime configuration*

Web: `web/lib/runtimeResilience.ts` — `formatOperationalError`.  
Tests: `tests/test_operator_error_copy.py`.

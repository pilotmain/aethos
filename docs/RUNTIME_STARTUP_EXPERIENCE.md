# Runtime startup experience

Progressive stages shown during cold hydration:

1. Starting runtime
2. Loading workers
3. Loading operational memory
4. Loading governance timeline
5. Loading runtime intelligence
6. Runtime ready

**APIs:** `GET /api/v1/runtime/startup`, `/runtime/readiness`, `/runtime/hydration/stages`

Office displays startup banner when `partial_mode` is true. Cached snapshot fallback prevents false “API unreachable” panics.

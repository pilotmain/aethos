# Mission Control degraded mode

When runtime hydration or individual panels fail, Office and intelligence pages show operational banners instead of white-screen errors. Cached truth may be served with `stale` status.

See `web/lib/runtimeResilience.ts` and `GET /api/v1/mission-control/state` resilient wrapper.

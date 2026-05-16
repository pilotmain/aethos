# Production surface lock

Surfaces locked for release candidate:

| Surface | Lock |
|---------|------|
| `/api/v1/mission-control/office` | Summary-first, progressive hydration |
| `/api/v1/runtime/capabilities` | Registry-driven discovery |
| `/api/v1/setup/certify` | One-curl + ready-state |
| `/api/v1/runtime/release-candidate` | RC certification |

Truth embed: `operational_freeze_lock` + `production_surface_lock` on runtime evolution Step 14.

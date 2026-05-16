# Mission Control UI deprecation plan (Phase 3 Step 4)

## Deprecated routes

| Route | Status | Replacement |
|-------|--------|-------------|
| `/mission-control/ceo` | Legacy (banner + sidebar) | `/mission-control/office` |
| `/mission-control/overview` | Retained as **Runtime** | Same path, primary nav label "Runtime" |
| `/mission-control/advanced` | Retained as **Settings** | Same path |

## Merged / consolidated surfaces

| Before | After |
|--------|--------|
| CEO agent cards + Office orchestrator | **Office** owns orchestrator + runtime workers |
| Duplicate runtime metrics on CEO + Overview | **Runtime** + cached `runtime_truth` |
| Raw governance audit dump | **Governance** timeline (`build_governance_timeline`) |

## Removed components

None in this step (routes deprecated in place). Future removal targets:

- CEO-specific cost/agent tables once Office exposes equivalent summaries
- Redundant runtime panel duplicates on Overview when Office covers them

## Primary navigation (stable)

Office · Runtime · Deployments · Providers · Marketplace · Privacy · Governance · Settings

Secondary (**More**): Runtime plugins, Advantages, CEO (legacy), Team, Budget, Approvals, Audit logs, Improvements

## Future removals

1. `/mission-control/ceo` — after one release with Office parity for cost/health
2. Duplicate provider cards on Overview if Providers page is sufficient
3. `missionControlNavItems` combined export in `web/lib/navigation.ts`

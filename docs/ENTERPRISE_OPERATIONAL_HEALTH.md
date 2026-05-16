# Enterprise operational health (Phase 3 Step 11)

Ten health categories, each: `healthy` | `warning` | `degraded` | `recovering` | `critical`

| Category | Source |
|----------|--------|
| runtime | `runtime_health` |
| provider | provider failures / panels |
| deployment | deployment pressure |
| automation | failed automation packs |
| governance | enterprise operational state |
| worker | worker reliability signals |
| workspace | workspace confidence |
| continuity | recovery active |
| recommendation_confidence | avg recommendation confidence |
| privacy | privacy posture |

Overall health is the worst active category level.

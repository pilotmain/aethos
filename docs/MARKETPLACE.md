# Runtime plugin marketplace (Phase 3 Step 1)

Operational plugin catalog separate from ClawHub skills (`/api/v1/marketplace/search`).

## APIs

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/marketplace/plugins` | Catalog + summary |
| GET | `/api/v1/marketplace/plugins/{id}` | Plugin detail |
| POST | `/api/v1/marketplace/install` | Install to `~/.aethos/plugins/` |
| POST | `/api/v1/marketplace/uninstall` | Remove install |
| POST | `/api/v1/marketplace/upgrade` | Reinstall with new version |

Owner privileges required for mutating routes.

## Install path

```text
~/.aethos/plugins/{plugin_id}/manifest.json
```

Runtime state tracks `installed_plugins` and `plugin_governance_audit`.

## Catalog

Bundled catalog: `data/aethos_marketplace/runtime_plugins.json`.

## Mission Control

Web: `/mission-control/plugins` — installed, available, health, permissions.

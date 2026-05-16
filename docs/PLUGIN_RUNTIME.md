# Plugin runtime (Phase 3 Step 1)

## Lifecycle

```text
discover → install → validate → load → activate → disable → uninstall → upgrade
```

## States

`registered`, `installed`, `loaded`, `active`, `warning`, `failed`, `disabled`, `deprecated`

## Modules

| Module | Role |
|--------|------|
| `plugin_manifest.py` | Schema |
| `plugin_registry.py` | Built-in + registered manifests |
| `plugin_installer.py` | Disk install under `~/.aethos/plugins/` |
| `plugin_runtime.py` | Safe load / health panel |
| `automation_packs.py` | Pack metadata from plugins |

## APIs

- `/api/v1/plugins/*` — load / disable / bootstrap
- `/api/v1/marketplace/*` — install / uninstall / upgrade

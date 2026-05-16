# Plugins (Phase 2 Step 8)

AethOS uses a lightweight plugin manifest layer — execution stays in the core runtime and provider gateway.

## Layout

- `app/plugins/plugin_manifest.py` — manifest schema
- `app/plugins/plugin_registry.py` — built-in provider/channel manifests
- `app/plugins/plugin_loader.py` — bootstrap
- `app/plugins/plugin_runtime.py` — capability host (no arbitrary code execution)
- `app/services/plugins/registry.py` — tool registration (existing)

## Manifest example

```json
{
  "plugin_id": "vercel-provider",
  "name": "Vercel",
  "version": "1.0.0",
  "capabilities": ["deployments", "logs", "redeploy"],
  "permissions": ["provider.vercel"]
}
```

API: `GET /api/v1/mission-control/plugins`

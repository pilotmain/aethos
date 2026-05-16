# Runtime plugins vs skill marketplace

AethOS separates two extension models:

## Runtime plugins

- **Purpose:** Extend **operational** capability (deploy hooks, provider adapters, repair flows, health checks).
- **Install path:** `~/.aethos/plugins/` via `/api/v1/marketplace/plugins` and Mission Control **Runtime plugins** (`/mission-control/plugins`).
- **Ownership:** Runtime / orchestrator loads plugins; governance records install actions.
- **Lifecycle:** Installed, health-checked, permission-scoped; not conversational personas.

## Skills (ClawHub-style marketplace)

- **Purpose:** Extend **AI execution** capability (tools, prompts, skill packs for agents).
- **Install path:** Skill registry APIs and Mission Control **Marketplace** (`/mission-control/marketplace`).
- **Ownership:** Brain / agent execution layer; sandbox and allowlist apply.
- **Lifecycle:** Versioned skill packages; install/update/uninstall per owner policy.

## Operator rule

```text
Runtime plugins extend operational capability.
Skills extend AI execution capability.
```

Do not merge these UIs: plugins answer “what can the platform do?”; skills answer “what can the model invoke?”

## APIs

| Surface | API prefix |
|---------|------------|
| Runtime plugins | `/api/v1/marketplace/plugins` |
| Skills | `/api/v1/mission-control/marketplace` (and ClawHub-compatible registry) |
| Truth snapshot | `build_runtime_truth()` → `plugins` + `marketplace` keys |

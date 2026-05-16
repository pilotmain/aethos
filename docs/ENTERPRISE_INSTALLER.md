# Enterprise installer (Phase 4 Step 10)

One authoritative setup path:

```text
curl … | bash  →  scripts/setup.sh  →  aethos setup
```

**Modes:** local-only, cloud-only, hybrid, later (via `AETHOS_ROUTING_MODE`).

**CLI:** `aethos setup doctor`, `aethos setup validate`, `aethos setup onboarding`

**API:** `GET /api/v1/setup/status`

Detects git, docker, ollama, vercel, gh, railway, fly, node, python. Validates API, Mission Control, env, and onboarding profile.

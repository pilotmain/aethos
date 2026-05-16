# Enterprise setup

Phase 4 Step 4 upgrades one-curl install and `aethos setup` into an enterprise-grade first-run experience.

## One-curl install

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash
AETHOS_INSTALL_DIR=~/.aethos curl -fsSL ... | bash
```

## Setup wizard

```bash
aethos setup
aethos setup resume
aethos setup repair
aethos setup doctor
aethos setup validate
aethos setup onboarding
```

Sections include routing (local/cloud/hybrid), Mission Control connection, orchestrator onboarding, optional channels and web search, and health checks.

**API:** `GET /api/v1/setup/status` — see [ENTERPRISE_INSTALLER.md](ENTERPRISE_INSTALLER.md) (Phase 4 Step 10).

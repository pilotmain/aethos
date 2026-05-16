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
```

Sections include routing (local/cloud/hybrid), Mission Control connection, optional channels and web search, onboarding profile, and health checks.

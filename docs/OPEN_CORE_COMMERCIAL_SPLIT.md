# Open core vs proprietary split (implementation guide)

This document complements **[OPEN_CORE_EXTENSIONS.md](OPEN_CORE_EXTENSIONS.md)** with a **repository and packaging** plan: AGPL-class core (public trust), commercial **Pro** layer (private package), plus optional encrypted artifacts.

## Current state in *this* repository

- **License (whole tree):** Apache-2.0 — see root `LICENSE`.
- **Commercial gating:** signed license tokens and feature IDs — `app/services/licensing/` and env `NEXA_LICENSE_KEY` / `NEXA_LICENSE_PUBLIC_KEY_PEM` (see OPEN_CORE_EXTENSIONS.md).
- **Extension imports:** `nexa_ext.*` via `app.services.extensions.get_extension` (preferred for app integration).
- **Pro plugin namespace (new):** `aethos_core.plugin_manager.PluginManager` loads `aethos_pro.<module>` when the commercial wheel is installed.

## Target layout (two repos)

| Repository | License | Contents (examples) |
|------------|---------|---------------------|
| **aethos-core** (public) | AGPL-3.0 for published *core* artifact (see `LICENSE.AGPL` reference) | PyPI/GitHub package ``aethos-core`` (Python import ``aethos_core``); see ``requirements.txt`` in this monorepo |
| **aethos-pro** (private) | Commercial | Goal/healing/negotiation modules you keep closed; ship as `aethos_pro` on a **private** index |

Until you split git history, keep developing in the monorepo and **extract** when stable.

## Plugin loading

1. **App code:** continue using `nexa_ext` for first-party hooks already wired in the codebase.
2. **Packaged SDK / extracted core:** use `PluginManager.load_proprietary("module_name", fallback=oss_impl)` so OSS users get `fallback` and Pro customers get `aethos_pro.module_name`.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `AETHOS_LICENSE_KEY` | Aliases to `NEXA_LICENSE_KEY` (see `app/core/aethos_env.py`) — signed token when using built-in verifier |
| `AETHOS_PRO_ENABLED` | Opt-in flag: allow runtime to treat Pro paths as enabled when license + package align (`Settings.aethos_pro_enabled`) |

## Publishing (outline)

- **OSS:** `python -m build` → upload `aethos-core` (or current name) to **public** PyPI.
- **Pro:** same tooling → upload to **private** index; customers configure `pip.conf` / `UV_INDEX`.

## Encrypted wheels / artifacts

`scripts/build_pro_package.py` encrypts a **single file** with Fernet for internal packaging workflows. Decryption and loader integration are distribution-specific — keep keys out of git.

## Verification snippet

```python
from aethos_core import PluginManager

if PluginManager.is_pro_available():
    mod = PluginManager.load_proprietary("example", fallback=None)
```

## Proprietary components (product messaging)

The following are **not** committed as a separate closed repo in this workspace; list them in **README** and sales collateral:

- Advanced goal planning (beyond OSS defaults)
- Packaged self-healing / enterprise extensions sold separately
- Inter-agent negotiation algorithms shipped in Pro builds
- Enterprise-only surfaces (RBAC, SSO, etc.) — see `app/services/licensing/features.py`

**Contact for commercial licensing:** set in README (e.g. `license@aethos.ai`).

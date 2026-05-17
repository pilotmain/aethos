# Canonical install path

**Public (recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
```

**Flow:**

```text
install.sh → scripts/setup.sh → aethos setup → enterprise extensions → Mission Control bootstrap
```

**Local recovery (not the public command):**

```bash
bash scripts/setup.sh
```

**Deprecated:** running `python scripts/setup.py` for the old numbered wizard UX. It now delegates to `aethos setup` unless `AETHOS_SETUP_LEGACY=1` or `--legacy-wizard`.

**Internal:** `AETHOS_SETUP_DRY_RUN=1` on `scripts/setup.sh` prints the command without running it.

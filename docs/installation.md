# Installation

## One-curl install (recommended)

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash
```

Default install directory is **`~/.aethos`** (override with `NEXA_INSTALL_DIR`).

### With Pro license string (runtime / wizard)

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash -s -- --license 'YOUR_KEY'
```

Private PyPI wheels (optional): see root [README.md](../README.md) and `AETHOS_PYPI_INSTALL_*` env vars in `scripts/install_aethos.sh`.

## Manual installation

```bash
git clone https://github.com/pilotmain/aethos.git
cd aethos
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
aethos setup
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

Use **`python -m aethos_cli setup`** if `aethos` is not on `PATH` yet.

## Requirements

- **Python 3.10+** (see `pyproject.toml`)
- **Git**
- **(Optional)** Docker — for the full Postgres + API + bot stack ([SETUP.md](SETUP.md))

## Next steps

- [Configuration](configuration.md)
- [SETUP.md](SETUP.md) for Docker, ports, and health checks

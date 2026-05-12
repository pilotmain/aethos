# Developer setup

## Prerequisites

- **Python 3.10+**
- **Git**
- **(Optional)** Docker — for parity with production-style stacks ([SETUP.md](../SETUP.md))

## Clone and install

```bash
git clone https://github.com/pilotmain/aethos.git
cd aethos
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

## Running tests

```bash
pytest
```

Targeted runs: `pytest tests/test_sandbox_execution.py -q`

## Running the API

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

## Code quality

This repo configures **Ruff** in `pyproject.toml` (imports / selected rules). Formatting may use team conventions — run `ruff check app tests` from the venv.

## More

- [DEVELOPMENT_HANDOFF.md](../DEVELOPMENT_HANDOFF.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)

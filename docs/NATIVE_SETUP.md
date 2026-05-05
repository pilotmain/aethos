# Native setup (Option 1)

Run Nexa **without Docker**: Python venv, local `.env`, optional **Ollama**, and the **`nexa_cli`** helpers.

## One-command native install

The repo root **`install.sh`** forwards to **`scripts/install.sh`** (Phase 55/56 bootstrap: clone optional, `nexa_bootstrap.py`, Docker/host start). For **nexa-next-only** native setup (venv + `pip install -r requirements.txt` + **`python -m nexa_cli setup`**), use:

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
```

Defaults clone to `~/nexa-next`. Override:

```bash
export NEXA_INSTALL_DIR="$HOME/code/nexa-next"
export NEXA_REPO_URL="https://github.com/pilotmain/nexa-next.git"
curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
```

Already cloned? From the repo root:

```bash
NEXA_USE_CURRENT_REPO=1 bash scripts/install_nexa_next_native.sh
```

## Interactive wizard

```bash
cd /path/to/nexa-next
source .venv/bin/activate   # create with: python3 -m venv .venv && pip install -r requirements.txt
python -m nexa_cli setup
```

The wizard:

- Sets **`NEXA_WORKSPACE_ROOT`** / **`HOST_EXECUTOR_WORK_ROOT`** to your projects folder.
- Configures **LLM** (Ollama with auto-detection via `ollama list`, or OpenAI / Anthropic / DeepSeek keys via hidden prompts).
- Upserts keys into **`.env`** (existing unrelated lines stay).
- Backs up `.env` to **`.env.bak`** when overwriting (same directory).

## Run the API

```bash
python -m nexa_cli serve
```

Default listen address: **`0.0.0.0:8010`** (matches common docker-compose host port mapping). Override:

```bash
NEXA_SERVE_PORT=8120 python -m nexa_cli serve --reload
```

The CLI loads **`.env`** from the repo root so **`NEXA_API_BASE`** / **`API_BASE_URL`** set during setup apply to `nexa run`, `nexa state`, etc.

## Requirements

- **PostgreSQL** is optional for quick tries (tests and some scripts use SQLite via `NEXA_NEXT_LOCAL_SIDECAR`). Production-style stacks still use Postgres — see `docker-compose.yml` and project README.
- **Ollama**: install from [ollama.ai](https://ollama.ai); wizard runs `ollama list` when you pick the local provider.

## Security

Never commit real API keys. The wizard writes only to your local `.env`.

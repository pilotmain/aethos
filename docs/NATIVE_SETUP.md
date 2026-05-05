# Native setup (Option 1)

Run Nexa **without Docker**: Python venv, local `.env`, optional **Ollama**, and the **`nexa_cli`** helpers.

## One-command native install (Phase 25 UX — Phase 32 refreshed UX)

The repo root **`install.sh`** forwards to **`scripts/install.sh`** (Phase 55/56 bootstrap: clone optional, `nexa_bootstrap.py`, Docker/host start). For **nexa-next-only** native setup (``.venv`` + `pip install -r requirements.txt` + **`python -m nexa_cli setup`**), use:

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
```

When you host a short URL (e.g. **`https://nexa.ai/install`**), point it at this script so **`curl … | bash`** stays one line.

This only works if the repo is **public** (or you pass GitHub auth). If **`curl` returns 404**, GitHub is usually hiding a **private** repo from anonymous raw access — use [Clone first (private or when curl 404)](#clone-first-private-or-when-curl-404) below.

**Default clone/update directory** is **`~/.nexa`** (override with **`NEXA_INSTALL_DIR`**). The Phase 32 installer prints **six labeled steps**: prerequisites (Python, Git, optional Node/Ollama), install directory + disk space, existing-folder actions, then clone/venv/`pip install`, then launches the interactive wizard with **`NEXA_SETUP_FROM_INSTALLER=1`** (wizard steps 3–6: LLM provider, API keys, features, save). It exports **`NEXA_SETUP_KIND`** for the wizard (`fresh` | `update` | `repair`).

```bash
export NEXA_INSTALL_DIR="$HOME/code/nexa"
export NEXA_REPO_URL="https://github.com/pilotmain/nexa-next.git"
curl -fsSL https://raw.githubusercontent.com/pilotmain/nexa-next/main/scripts/install_nexa_next_native.sh | bash
```

### Clone first (private or when curl 404)

Use the same installer **from a local checkout** (SSH or HTTPS with your credentials):

```bash
git clone https://github.com/pilotmain/nexa-next.git "${HOME}/nexa-next"
cd "${HOME}/nexa-next"
bash scripts/install_nexa_next_native.sh
```

If you already have the repo on disk, set `NEXA_USE_CURRENT_REPO=1` so it does not clone again:

```bash
cd /path/to/nexa-next
NEXA_USE_CURRENT_REPO=1 bash scripts/install_nexa_next_native.sh
```

## Interactive wizard

```bash
cd /path/to/nexa-next
source .venv/bin/activate   # create with: python3 -m venv .venv && pip install -r requirements.txt
python -m nexa_cli setup
```

The wizard:

- Shows a **banner**, **environment line**, and (unless **`NEXA_SETUP_FROM_INSTALLER=1`**) boxed **Step 1–2**: prerequisites + repo/disk + **installation type** (fresh / update / repair — installer can pre-select via **`NEXA_SETUP_KIND`**).
- **Steps 3–5**: **LLM provider**, **API keys** (primary + optional cross-provider keys with validation where possible), **workspace path**, **feature toggles** (number-to-toggle checklist per feature), **`NEXA_API_BASE`**.
- Sets **`NEXA_WORKSPACE_ROOT`** / **`HOST_EXECUTOR_WORK_ROOT`** to your projects folder.
- Configures **LLM** (Ollama with model list + default model, or OpenAI / Anthropic / DeepSeek with optional validation).
- **Feature toggles** map to **`NEXA_*` flags** (host executor, browser, cron, social, PR review, scraping).
- Upserts keys into **`.env`** (existing unrelated lines stay).
- Backs up `.env` to **`.env.bak`** when overwriting (same directory).
- **Repair** runs `pip install -r requirements.txt` before writing `.env`.
- Finishes with a **success panel** (`nexa_cli/welcome.py`) and a **quick API ping** (non-fatal if the server is not running yet).

### CLI helpers after install

| Command | Purpose |
|---------|---------|
| `python -m nexa_cli status` | GET `/api/v1/health` and `/api/v1/system/health` using **`NEXA_API_BASE`** (default `http://127.0.0.1:8010`). |
| `python -m nexa_cli features` | Summarize enabled capability flags from repo **`.env`**. |
| `python -m nexa_cli config` | Print path to **`.env`**; use **`--edit`** with **`$EDITOR`** to open it. |

## Run the API

```bash
python -m nexa_cli serve
```

Default listen address: **`0.0.0.0:8010`** (matches common docker-compose host port mapping). Override:

```bash
NEXA_SERVE_PORT=8120 python -m nexa_cli serve --reload
```

The CLI loads **`.env`** from the repo root so **`NEXA_API_BASE`** / **`API_BASE_URL`** set during setup apply to HTTP subcommands (`state`, `run`, `status`, etc.). Defaults use port **8010** for new setups.

## Requirements

- **PostgreSQL** is optional for quick tries (tests and some scripts use SQLite via `NEXA_NEXT_LOCAL_SIDECAR`). Production-style stacks still use Postgres — see `docker-compose.yml` and project README.
- **Ollama**: install from [ollama.ai](https://ollama.ai); wizard runs `ollama list` when you pick the local provider.

## Security

Never commit real API keys. The wizard writes only to your local `.env`.

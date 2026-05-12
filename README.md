# AethOS — The Agentic Operating System

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Commercial License](https://img.shields.io/badge/License-Commercial-red.svg)](LICENSE.commercial)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

## One-curl install

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash
```

With a Pro / license string for the installer (optional):

```bash
curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash -s -- --license 'YOUR_KEY'
```

Default install path is often `~/.aethos`. For a manual clone of this repo, see [docs/installation.md](docs/installation.md).

## Quick start

```bash
cd ~/.aethos   # or your clone directory
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

When the web app is running locally, open [http://localhost:3000](http://localhost:3000) (or the port shown in your setup). See [docs/WEB_UI.md](docs/WEB_UI.md) and [docs/SETUP.md](docs/SETUP.md) for URLs and auth.

## Features

- **Natural language agents** — create and orchestrate specialists from chat  
- **File operations** — read, write, and modify files within policy  
- **Command execution** — allowlisted / supervised shell flows  
- **Safe sandbox** — approval-based plans with rollback where enabled  
- **Deploy helpers** — Vercel, Railway, Fly.io, and others when CLIs and tokens are configured  
- **Observability** — status, metrics, and health surfaces where enabled  

## Documentation

Full index: [docs/README.md](docs/README.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

- **Open source:** [Apache License 2.0](LICENSE)  
- **Commercial:** Pro / enterprise — [LICENSE.commercial](LICENSE.commercial)  

Contact: [license@aethos.ai](mailto:license@aethos.ai)

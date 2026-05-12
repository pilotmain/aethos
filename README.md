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

## Legal notice (read before use)

**Disclaimer of warranty**

AETHOS IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**User responsibility**

By using AethOS, you acknowledge that:

- You are solely responsible for the configuration, deployment, and actions of any AI agents you create  
- You assume risks associated with autonomous or semi-autonomous agent operations  
- The software may perform file operations, run commands, or take other actions that could affect your systems and data  
- You should review and approve planned actions before execution when approval gates are available  

**No liability for AI agent actions**

The AethOS maintainers and contributors are **not** responsible for damages, data loss, or system issues resulting from use of AI agents deployed with this software, **to the extent permitted by law**. You are responsible for monitoring, approving, and managing agent activities in your environment.

Additional terms: see [LICENSE.disclaimer](LICENSE.disclaimer) and [docs/legal.md](docs/legal.md).

# AethOS — OpenClaw parity-first agentic operating system

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE) [![Commercial License](https://img.shields.io/badge/License-Commercial-red.svg)](LICENSE.commercial) [![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)

## Primary objective

AethOS is currently in a **strict OpenClaw parity phase**.

The objective is to reproduce OpenClaw exactly as it works today before prioritizing privacy, PII filtering, local-first differentiation, cost transparency, or custom AethOS-specific architecture.

During this phase:

- every feature should map to a concrete OpenClaw behavior;
- every architectural decision should reduce the gap to OpenClaw parity;
- privacy/PII/local-first improvements are Phase 2 unless they are required for current OpenClaw-compatible behavior;
- major refactors and novel UX/orchestration patterns should wait until parity is verified.

See [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md), [docs/OPENCLAW_PARITY_AUDIT.md](docs/OPENCLAW_PARITY_AUDIT.md), and [docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md) (master implementation plan).

## One-curl install

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash
```

With a Pro / license string for the installer (optional):

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/pilotmain/aethos@main/install.sh | bash -s -- --license 'YOUR_KEY'
```

Default install path is often `~/.aethos`. For a manual clone of this repo, see [docs/installation.md](docs/installation.md).

## Quick start

```bash
cd ~/.aethos   # or your clone directory
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8010
```

When the web app is running locally, open [http://localhost:3000](http://localhost:3000) or the port shown in setup. See [docs/WEB_UI.md](docs/WEB_UI.md) and [docs/SETUP.md](docs/SETUP.md) for URLs and auth.

## Parity surfaces

- Natural language agents and specialist orchestration
- File operations inside configured workspace policy
- Command execution and host tool flows
- Browser/tool-use gates
- Durable memory and context surfaces
- Mission Control operator UI
- Deployment helpers for configured providers
- Multi-agent, long-running, and autonomous workflow surfaces
- Channel adapters where OpenClaw-compatible behavior is required

## Development rule

Do not introduce architectural divergence unless required to reproduce OpenClaw behavior.

Before opening a PR, run:

```bash
python -m compileall -q app
pytest
pytest tests/test_openclaw_parity.py
pytest tests/test_openclaw_*_parity.py
pytest tests/test_openclaw_doctrine_docs.py
```

Each PR should state which OpenClaw behavior it reproduces and which parity checkpoint it advances.

## Documentation

Full index: [docs/README.md](docs/README.md)

Key parity docs:

- [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md)
- [docs/OPENCLAW_PARITY_AUDIT.md](docs/OPENCLAW_PARITY_AUDIT.md)
- [docs/MIGRATING_FROM_OPENCLAW.md](docs/MIGRATING_FROM_OPENCLAW.md)
- [docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md](docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

- **Open source:** [Apache License 2.0](LICENSE)
- **Commercial:** Pro / enterprise — [LICENSE.commercial](LICENSE.commercial)

Contact: [license@aethos.ai](mailto:license@aethos.ai)

## Legal notice (read before use)

**Disclaimer of warranty**

AETHOS IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NONINFRINGEMENT.

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

**User responsibility**

By using AethOS, you acknowledge that:

- You are solely responsible for the configuration, deployment, and actions of any AI agents you create.
- You assume risks associated with autonomous or semi-autonomous agent operations.
- The software may perform file operations, run commands, or take other actions that could affect your systems and data.
- You should review and approve planned actions before execution when approval gates are available.

**No liability for AI agent actions**

The AethOS maintainers and contributors are not responsible for damages, data loss, or system issues resulting from use of AI agents deployed with this software, to the extent permitted by law.

You are responsible for monitoring, approving, and managing agent activities in your environment. Additional terms: see [LICENSE.disclaimer](LICENSE.disclaimer) and [docs/legal.md](docs/legal.md).

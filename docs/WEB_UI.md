# Web UI

The Nexa **web app** (Next.js) is started alongside the API when you use `run_everything.sh` and Node is available, typically on **port 3000** (see the script banner; your `.env` may set `NEXA_WEB_BASE_URL`).

- **Chat** — same orchestration and agents as Telegram: `@marketing`, `@research`, `@dev`, co-pilot “Next steps” continuation, and natural routing.
- **Context** — conversation and rolling topic state align with the Telegram path where the same app user is linked.
- **Documents** — generate exports (e.g. PDF, Word) from assistant messages; link to the Docs area when artifacts are created.
- **Metadata** — for public web and marketing analysis, responses can show tool lines (e.g. public read + search) and sources without a separate “browser” product surface.

The API serves OpenAPI at `http://localhost:8000/docs` when the stack is up.

For setup and environment variables (web search, public URL read, etc.), see [SETUP.md](SETUP.md).

Host **permission cards** (Allow once / session / Deny) and workspace policy (`NEXA_WORKSPACE_STRICT`, Docker paths): [WORKSPACE_AND_PERMISSIONS.md](WORKSPACE_AND_PERMISSIONS.md).

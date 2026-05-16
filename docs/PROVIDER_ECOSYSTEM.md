# Provider ecosystem (Phase 3 Step 1)

Providers are **plugins**, not hardcoded orchestrator branches.

## Built-in registry targets

Vercel, Railway, Fly, Netlify, Cloudflare, GitHub, Discord, Slack, Telegram.

## Catalog extensions (installable)

Linear, deployment automation packs, and additional targets listed in `runtime_plugins.json`.

## Rules

- Provider-routed execution via brain selection
- Privacy-aware routing (`local_first`, `local_only`)
- Observable via Mission Control provider panels and traces

# Migrating from OpenClaw-style setups to Nexa-next

This guide is for teams evaluating Nexa-next as a **privacy-first, cost-aware** assistant stack. It avoids absolute claims: capabilities depend on your `.env`, hardware, and chosen channels.

## What you can expect to map across

- **Chat channels**: Nexa supports Telegram (and optional Slack/Discord foundations). Wire `TELEGRAM_BOT_TOKEN` and the API base URL your web UI uses.
- **Skills-like behavior**: Nexa stores user-defined skill JSON under `data/nexa_skills/` and can load packaged manifests. Installation still requires validation and review—there is no silent install from the open internet in the defaults.
- **Autonomy**: Scheduler + autonomy loops exist, but safe defaults expect explicit approvals for high-impact paths (especially in regulated workspace mode).

## What is intentionally different

- **Outbound calls** are gated by a privacy firewall and optional network allowlists. If you relied on unconstrained tool egress, you must model grants explicitly.
- **Cost controls**: Token budgets and blocking are first-class. Remote LLM calls fail closed when budgets or strict privacy modes demand it.
- **Sandboxing**: Full micro-VM isolation is **not** claimed in this repository yet. The Phase 54 sandbox module exposes modes honestly (`process` today; `docker` when available).

## Suggested migration checklist

1. Copy `.env.example` → `.env`; set `NEXA_SECRET_KEY` for any shared host.
2. Enable **one channel** first (Telegram) before turning on autonomy features.
3. Set `NEXA_STRICT_PRIVACY_MODE=true` until you confirm which providers may receive data.
4. Run `./scripts/install_check.sh` and `./scripts/nexa_doctor.sh` from the repo root.
5. Open Mission Control and confirm **Safety & readiness** matches your expectations.

## Honest limitations

- Nexa-next does **not** ship a SOC 2 report, enterprise SSO, or guaranteed micro-VM isolation in-tree as of Phase 54.
- Voice and multimodal paths are **partial**: stubs exist so operators can see posture in Mission Control; production ASR/vision requires additional setup.

If something you need is missing, treat it as a product gap to validate—not a hidden toggle.

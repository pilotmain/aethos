# Slack integration (Phase 12.1)

Nexa supports Slack in two ways — pick **one primary transport** per workspace to avoid duplicate processing:

| Transport | Use case | Requirements |
| --------- | -------- | ------------ |
| **HTTP Events API** | Production behind a public HTTPS URL | `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, Request URLs pointing at `{API_BASE_URL}{API_V1_PREFIX}/slack/events` |
| **Socket Mode (Bolt)** | Local dev, firewalls, no public URL | `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` (`xapp-…`), `SLACK_SIGNING_SECRET` recommended, **`NEXA_SLACK_ENABLED=true`** |

The FastAPI routes in `app/api/routes/slack.py` implement Events API + interactive components. The Bolt client in `app/channels/slack/bot.py` runs as a **background task** when `NEXA_SLACK_ENABLED=true` and `SLACK_APP_TOKEN` is set.

## Environment variables

| Variable | Purpose |
| -------- | ------- |
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (`xoxb-…`) |
| `SLACK_SIGNING_SECRET` | Verifies HTTP requests from Slack (Events + Interactions). Still recommended for Bolt. |
| `SLACK_APP_TOKEN` | App-level token for Socket Mode (`xapp-…`). Required only for Socket Mode. |
| `NEXA_SLACK_ENABLED` | When `true`, start the Bolt Socket Mode client inside the API process. |
| `NEXA_SLACK_ROUTE_INBOUND` | When `true`, Slack inbound uses `slack_inbound_via_gateway` → `route_inbound` (same funnel as Discord gateway tests). |
| `NEXA_SLACK_REACTIONS_ENABLED` | When `true`, `reaction_added` events are summarized and sent through the gateway (off by default; noisy). |

## Slash command `/nexa`

The Socket Mode handler registers `/nexa`. Create the slash command in your Slack app (Slash Commands) pointing at the same app; Bolt receives the payload without an extra HTTP endpoint when using Socket Mode.

## Permissions (interactive buttons)

Permission cards reuse `app/services/channel_gateway/slack_blocks.py`. Wire **Interactivity** to `{API}/api/v1/slack/interactions` so button actions resolve even when chat messages arrived over Socket Mode.

## Operations checklist

1. Create a Slack app, enable **Socket Mode** (if using Bolt), add **Bot Token Scopes** (`chat:write`, `app_mentions:read`, `channels:history`, `im:history`, `reactions:read` as needed).
2. Install the app to your workspace; copy `xoxb` and `xapp` tokens.
3. Set `.env` and restart the API (`uvicorn`). Confirm logs show the Socket Mode task or HTTP requests hitting `/slack/events`.

## Related code

- `app/channels/base.py` — `NexaChannel` abstraction  
- `app/channels/slack/` — Bolt handlers + `SlackSocketNexaChannel`  
- `app/services/channel_gateway/slack_adapter.py` — normalized message shape  
- `docs/CHANNEL_GATEWAY.md` — gateway design context  

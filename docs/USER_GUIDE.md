# Nexa Next — User Guide

This guide is for anyone running Nexa Next day to day: missions, Mission Control, privacy modes, and troubleshooting.

## Missions

A **mission** is a structured unit of work Nexa orchestrates across agents (research, coding, review, etc.). Missions are persisted in the database with:

- **Mission row** — title, status, optional input text.
- **Tasks** — per-agent steps (queued → running → completed).
- **Artifacts** — outputs recorded for handoff and auditing.

Typical flow:

1. You describe a goal (web dashboard, Telegram, or API).
2. Nexa parses intent, creates a mission and tasks, and runs agents within configured timeouts.
3. Mission Control shows graph, events, privacy signals, and artifacts.

### Export / import

Authenticated HTTP APIs:

- `GET /api/v1/mission-control/export/{mission_id}` — JSON bundle (mission + tasks + artifacts).
- `POST /api/v1/mission-control/import` — body is the same bundle shape; creates a **new** mission id owned by your user.

Exports are scoped: you cannot export another user’s mission.

## Privacy modes

Privacy stance combines:

1. **Per-user setting** (recommended) — `GET`/`POST /api/v1/user/settings` with `privacy_mode`.
2. **Environment default** — `NEXA_USER_PRIVACY_MODE` when no DB row exists.

Modes:

| Mode | Meaning |
|------|---------|
| **standard** | Balanced egress detection (Phase 18 calibration). |
| **strict** | Medium-confidence secret-shaped findings are elevated to blocking behavior. |
| **paranoid** | Only `local_stub` providers; outbound PII blocked at firewall; model output containing PII fails the call. |

Integrity alerts explain **why** something matched (reason, pattern summary, confidence). Warning-level alerts can be acknowledged via `POST /api/v1/mission-control/override-alert` (never secrets).

## Mission Control dashboard

Open the web **Mission Control** page after configuring API base URL and identity (`X-User-Id`; optional bearer if `NEXA_WEB_API_TOKEN` is set).

Panels:

- **Privacy & trust** — heuristic privacy score and mode reminder.
- **Provider transparency** — recent provider calls, blocks, redactions.
- **Graph / live events** — orchestration visibility.
- **Integrity banner** — critical vs warning; expandable “why” text.

Snapshot polling uses `/api/v1/mission-control/state?user_id=…`. Streams are **scoped per user** when `user_id` is supplied.

### Settings panel (web)

On desktop, Mission Control shows a **Settings** column on the right. On smaller screens, open **Settings** to use the same panel in a drawer.

You can adjust:

- **Privacy mode** — `standard`, `strict`, or `paranoid` (same semantics as the API; see [Privacy modes](#privacy-modes)).
- **Theme** — light or dark for the Mission Control shell (saved per user).
- **Auto refresh** — when on, the dashboard polls mission-control state on an interval; when off, refresh manually.

Changes call `GET`/`POST /api/v1/user/settings`. The UI shows saving progress and **Saved** / **Failed** feedback. Your configured **User id** appears in the header; changing identity in local storage (e.g. after login or switching users) reloads context.

## CLI (optional)

From the repo root:

```bash
python -m nexa_cli state --user-id YOUR_ID
python -m nexa_cli run "Your mission text here"
python -m nexa_cli settings get
python -m nexa_cli settings set privacy_mode=strict theme=dark auto_refresh=true
python -m nexa_cli replay MISSION_UUID
```

`settings set` accepts one or more `key=value` pairs. Supported keys: `privacy_mode`, `theme` (`dark` / `light`), `auto_refresh` (`true` / `false` / `1` / `0`).

`replay` posts to `/api/v1/mission-control/replay/{mission_id}` and prints the HTTP status and JSON body (missions must have stored `input_text`).

Environment:

- `NEXA_API_BASE` — API origin (default `http://127.0.0.1:8000`).
- `NEXA_CLI_USER_ID` — default `--user-id`.
- `NEXA_WEB_API_TOKEN` — if the API requires bearer auth.

## Performance expectations

- Mission Control refresh should stay responsive on a healthy LAN/dev setup (target **under ~500 ms** for `/mission-control/state` when the DB is local).
- If the UI feels slow, check database latency, network to the API, and browser devtools for failing requests.

## Troubleshooting

| Symptom | What to check |
|---------|----------------|
| `401` from API | Missing `X-User-Id` or wrong bearer token. |
| Empty privacy/provider streams | Pass `user_id` on `/mission-control/state`; events are tagged per user in Phase 20+. |
| Provider blocked | Review privacy mode, `NEXA_STRICT_PRIVACY_MODE`, `nexa_disable_external_calls`, and Mission Control integrity alerts. |
| Export 404 | Mission id wrong or not owned by your user. |

For developers: architecture overview remains in `docs/ARCHITECTURE.md`.

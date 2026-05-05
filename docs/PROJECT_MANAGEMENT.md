# Mission Control — Projects & Tasks (Phase 27)

Phase 27 adds **projects** (missions with goals), **tasks**, **checkout** (claim/unclaim), and a **mission tree** summary. Data lives in a dedicated SQLite file: `{NEXA_DATA_DIR}/mission_control.db` (not the main SQLAlchemy DB).

## Telegram commands

| Command | Purpose |
|---------|---------|
| `/goal` | Mission Control projects (`/goal "Goal text"`, `list`, `use <id>`, `status <id>`) |
| `/task` | `add`, `list` (scoped to **current** project when set via `/goal use`) |
| `/tasks` | All tasks visible for this **chat** scope |
| `/assign` | `/assign @Member "exact task title"` |
| `/claim` | `/claim @Agent "task"` when orchestration is on; otherwise `/claim "task"` |
| `/unclaim` | Same pattern |
| `/done` | `/done "title"` or `/done @Member "title"` |
| `/mission` | Progress bar + counts (defaults to current project) |
| `/mcstatus` | `/mcstatus @Member` — roster line + assigned tasks |

**Note:** `/project` is already used for **workspace / dev project keys** (`nexa_workspace_projects`). Mission Control uses **`/goal`** for goal-based projects.

## Environment

| Variable | Default | Meaning |
|----------|---------|---------|
| `NEXA_PROJECTS_ENABLED` | `true` | Master switch for Telegram handlers + controller usage |
| `NEXA_DATA_DIR` | `./data` | Directory containing `mission_control.db` |
| `NEXA_TASK_LOCK_TIMEOUT_SECONDS` | `3600` | Auto-release stale **checkout** locks |

## Integration

- **Team rosters** (Phase 26): assignments and `mcstatus` resolve members via `TeamRoster` / `AgentRegistry`. When `NEXA_AGENT_ORCHESTRATION_ENABLED=true`, `/assign` and `/claim` require real spawned agents; when off, stable synthetic ids (`tg:<telegram_user_id>`) are used for claim/done.

## Code layout

- `app/services/project/` — models, SQLite persistence, controller, mission tree, lock helpers
- `app/bot/project_commands.py` — Telegram handlers
- `tests/test_project_phase27.py`

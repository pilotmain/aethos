# Phase 29 — Multi-tenant RBAC (workspaces)

Technical **organizations** are surfaced as **workspaces**: isolated tenants with **roles** (Owner, Admin, Member, Viewer), optional **teams**, and **invites**.

## Storage

- **`{NEXA_DATA_DIR}/rbac.db`** — organizations, org memberships, invites, teams, team memberships, and **active workspace** pointer per user id string (e.g. Telegram numeric id).
- **`mission_control.db`** — nullable **`organization_id`** / **`team_id`** on `projects` and `tasks` (auto-migrated on store init).
- **`budget.db`** — nullable **`organization_id`** / **`team_id`** on `member_budgets` (auto-migrated on tracker init).

## Configuration

| Env | Meaning |
|-----|---------|
| `NEXA_RBAC_ENABLED` | When `true`, enables `/org` and Mission Control tagging by active workspace (default `false`). |

## Roles & permissions

Defined on `OrganizationMember.can()` in `app/services/rbac/models.py`:

- **Owner** — full org control including destructive actions mapped to permission strings.
- **Admin** — members + settings + projects/tasks/agents (no `delete_org` in the default matrix).
- **Member** — create projects, tasks, run agents, view.
- **Viewer** — read-only (`view_all`).

## Telegram

| Command | Purpose |
|---------|---------|
| `/org` | Help |
| `/org create "Name"` | Create workspace; creator becomes Owner and active workspace |
| `/org list` | Workspaces you belong to |
| `/org switch <slug>` | Set active workspace |
| `/org members` | Members of active workspace |
| `/org invite` | Create invite code (`/org join <code>`) |
| `/org role …` / `/org remove …` | Admin-style member management |
| `/org team create` / `/org team list` | Teams inside active org |

With **`NEXA_RBAC_ENABLED=true`**, new **`/goal`** projects in Mission Control receive the **active workspace** id when set (`app/bot/project_commands.py`). Listing **`/goal list`** filters to rows whose `organization_id` is null **or** matches the active workspace.

## Migration

For existing deployments that created databases before Phase 29:

```bash
python migrations/add_rbac_fields.py
```

Runtime startup also applies lightweight `ALTER TABLE` migrations for Mission Control and budget stores when possible.

## Resource isolation helpers

`ResourceIsolation` in `app/services/rbac/resource_filter.py` exposes membership checks and helpers for future API/query filtering (`organization_id` / `team_id` on domain rows).

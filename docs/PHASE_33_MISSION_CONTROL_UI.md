# Phase 33 — Mission Control UI redesign (implementation spec)

## 1. Goal

Evolve the Mission Control experience from a **dense, panel-heavy operator console** into a **professional product shell** (Paperclip / Linear / ClickUp idioms): clear hierarchy, card-based summaries, deliberate density controls, and progressive disclosure—without regressing power-user workflows already wired to the backend.

This phase is **frontend-first**. Backend gaps are called out explicitly.

---

## 2. Current state (repo facts)

### 2.1 Where Mission Control lives today

| Area | Location |
|------|----------|
| Next.js route | `web/app/mission-control/page.tsx` → `MissionControlLayout` |
| Primary UI | `web/components/mission-control/*` (many panels: graph, forge, autonomy, token economy, maintenance, etc.) |
| Snapshot cache | `web/lib/state/missionControlStore.ts` — parallel fetch `GET …/mission-control/graph` + `GET …/mission-control/state` |
| Live stream | `web/lib/ws/missionControlStream.ts` — WebSocket `…/mission-control/events/ws` |
| Types | `web/lib/nexa-types.ts` (`MissionControlSummary`, graph payloads, etc.) |

The backend Mission Control API is **`/api/v1/mission-control/*`** (`app/api/routes/mission_control.py`): `graph`, `state`, maintenance actions, gateway run, assignments, etc.

### 2.2 Stack today (`web/package.json`)

Already present: **Next.js 14**, **React 18**, **Tailwind**, **Lucide**.

**Not** present yet (add during Phase 33 if adopted):

- **shadcn/ui** — component primitives + Radix patterns  
- **TanStack Query** — server cache, retries, stale-while-revalidate  
- **Zustand** — optional fine-grained UI state (today Mission Control uses a small module-level store + subscribers)  
- **Recharts** — gauges, sparklines  
- **@dnd-kit** — Kanban drag-drop  

Treat these as **dependencies to introduce deliberately** (bundle budget + lint discipline), not as “already shipped.”

---

## 3. Design principles

1. **One shell, many views** — Single Mission Control “app” with consistent chrome (nav, context bar, command palette optional later), not unrelated pages without hierarchy.
2. **Progressive disclosure** — Default dashboard shows status + next actions; advanced panels remain reachable but not on first paint.
3. **Truth from APIs** — UI reflects `mission-control/state`, `graph`, and domain endpoints; avoid duplicate invented client models where OpenAPI/types exist.
4. **Accessible defaults** — Keyboard focus, contrast, reduced-motion respect for Framer usage already in `web/`.
5. **Ship incrementally** — Vertical slices (dashboard shell → work board → budget gauge) over a big-bang rewrite.

---

## 4. Information architecture

### 4.1 Recommended routes (Next.js `web/app`)

Prefer **nested routes under `/mission-control`** so existing bookmarks and links keep working:

```
/mission-control              → Overview dashboard (new default landing)
/mission-control/work        → Active work: Kanban / list (tasks + assignments TBD)
/mission-control/team        → Agents / org visualization (from MC graph + org APIs)
/mission-control/projects    → Workspace projects bridge (see §6)
/mission-control/budget      → Usage + budget gauges (providers usage + Phase 28 snapshot)
/mission-control/advanced    → Optional: relocate dense legacy panels here behind tabs
```

**Alternative:** Keep everything on one URL with hash or query-driven tabs (`?tab=…`). Prefer separate routes for shareability and deep links.

### 4.2 Legacy compatibility

- Preserve **`MissionControlLayout`** entry point; refactor internals into **shell + outlet** rather than deleting panels overnight.
- Optionally redirect **`/mission-control` → `/mission-control/overview`** once the new dashboard is default.

---

## 5. UX patterns (target experience)

| Intent | Pattern |
|--------|---------|
| “What needs attention?” | Top **attention strip** from `state.attention` / integrity alerts (already partially present) |
| “What’s running?” | **Active work** cards with live WS badges |
| “Who / what is deployed?” | **Team grid** from graph nodes + agent cards (upgrade `AgentCard` styling) |
| “Plan work” | **Kanban** columns with `@dnd-kit`; optimistic PATCH via tasks API where applicable |
| “Spend & limits” | **Gauge + sparkline** from `/providers/usage` summary + budget snapshot |
| “Goals hierarchy” | **Interactive mission tree** built from `/mission-control/graph` (collapse/expand, focus node) |

Avoid Telegram-parity copy in headings; use **product language** (Mission, Workstream, Assignment).

---

## 6. Backend mapping (what exists vs gaps)

### 6.1 Mission Control (ready)

| Capability | Endpoint |
|------------|----------|
| Mission DAG | `GET /api/v1/mission-control/graph` |
| Snapshot | `GET /api/v1/mission-control/state?hours=24` |
| Timeline | `GET /api/v1/mission-control/events/timeline` |
| Actions | POST routes under same router (reset, purge, gateway run, assignment cancel, …) |

### 6.2 Tasks (personal / checklist-style)

| Capability | Endpoint |
|------------|----------|
| List / CRUD | `/api/v1/tasks`, `/api/v1/tasks/{id}`, complete/snooze |

**Gap:** Kanban “columns” may require a **stable status field** or mapping convention if tasks schema does not match Todo / Doing / Done. Spec follow-up: confirm `TaskRead` / DB columns vs desired columns.

### 6.3 Workspace “projects” (Nexa workspace registry)

| Capability | Endpoint |
|------------|----------|
| List/create/delete Nexa workspace projects | `/api/v1/web/workspace/nexa-projects` |
| Active project | `/api/v1/web/workspace/active-project` |

These are **not** generic `/api/v1/projects`; Phase 33 UI should label them accurately (“Workspace projects”) unless a unified `/projects` façade is added server-side.

### 6.4 Budget / usage

| Capability | Endpoint |
|------------|----------|
| Provider usage + summary | `GET /api/v1/providers/usage` (`summary` includes budget-oriented snapshot per `snapshot_for_user`) |
| Mobile placeholder org budget | `GET /api/v1/mobile/orgs/{org_id}/budget-summary` (placeholder note in route) |

**Gap:** A dedicated **`GET /api/v1/budget`** façade may still help the UI if web clients must avoid assembling multiple summaries—optional backend Phase 33b.

### 6.5 Team / org chart

Potential sources:

- **Mission graph nodes** (agents, missions) — already fetched.
- **Governance / agent organizations** — `agent_organization` API (`/api/v1/agent-organizations/…`) if representing human/org structure.

**Gap:** True **org chart** data model may need backend aggregation if not derivable from existing payloads.

---

## 7. Frontend architecture

### 7.1 State

| Concern | Recommendation |
|---------|------------------|
| Server data | TanStack Query (`QueryClientProvider` in `web/app/layout.tsx` or segment layout) |
| MC snapshot | Migrate `missionControlStore` fetch logic into query hooks OR wrap existing store with query-driven refresh |
| Live WS | Keep `missionControlStream`; bridge events into query cache or small Zustand slice |

### 7.2 Component system

Introduce **shadcn/ui** incrementally:

1. `Button`, `Card`, `Tabs`, `DropdownMenu`, `Sheet`, `Badge`, `Progress`, `Skeleton`
2. Compose Mission Control-specific pieces in `web/components/mission-control/v2/` (name TBD) to avoid breaking imports during migration

### 7.3 Visualization

- **Recharts** for usage trends and donut/gauge-style charts (wrap in thin components under `web/components/mission-control/charts/`).
- **Mission graph** — evolve `MissionGraph.tsx` toward zoom/pan + collapsible clusters before committing to a heavy graph library (optional later: `@xyflow/react` if graph complexity grows).

### 7.4 Drag and drop

- **@dnd-kit** for Kanban **only after** task status semantics are confirmed.

---

## 8. Milestones (execution order)

### M1 — Shell & navigation (1–2 PRs)

- Mission Control **AppShell**: sidebar + header + content region.
- Move existing `MissionControlLayout` sections behind tabs or `/mission-control/advanced`.
- Establish **design tokens** (spacing, typography scale, semantic colors) aligned with Tailwind config.

### M2 — Overview dashboard

- Cards: attention items, active work, provider summary teaser, integrity alerts.
- Empty/error states using Skeleton + concise copy.

### M3 — Work board

- Kanban or swimlanes wired to `/api/v1/tasks` (or subset); optimistic updates.
- Detail drawer: assignee (if available), due date, links back to Mission Control entities.

### M4 — Team / agents view

- Grid of agents from graph + status indicators; reuse `AgentCard` logic with refreshed visuals.

### M5 — Budget & usage

- Dedicated `/mission-control/budget` using `/providers/usage` summary + thresholds for yellow/red states.

### M6 — Mission tree interaction

- Expand/collapse, focus mode, deep link to selected node id.

---

## 9. Non-goals (Phase 33)

- Replacing Telegram as the primary operator surface (still valuable for mobile).
- Full **Gantt** scheduling unless backend emits timeline spans (could be Phase 34+).
- Pixel-perfect clone of any external product—only **interaction idioms**.

---

## 10. Success criteria

- New operators reach **“what’s happening / what’s blocked”** within **one screen** without scrolling through dozens of equal-weight panels.
- Lighthouse: no major regressions on **performance** and **accessibility** for `/mission-control/*`.
- No duplicate polling storms: coordinate Mission Control refresh intervals with TanStack Query defaults.
- Feature parity checklist: existing dangerous maintenance actions remain **confirm-gated** and discoverable.

---

## 11. Open decisions (need product input)

1. **Default IA:** Single-page tabs vs nested routes (§4.1).
2. **Kanban source of truth:** `/tasks` only vs mixed with mission assignments from `state`.
3. **Whether to add** a thin `/api/v1/mission-control/dashboard` aggregator to reduce client fan-out.

Once these are answered, implementation tickets can be cut per milestone.

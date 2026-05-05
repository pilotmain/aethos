# Phase 28 — Work hours & budgets (token tracking)

Technical **tokens** are surfaced as **work hours** in Telegram copy: each member (sub-agent in the orchestration registry) has a **monthly limit**, metered usage, **warnings** near exhaustion, and **auto-pause** when the limit is reached.

## Storage

- SQLite database: `{NEXA_DATA_DIR}/budget.db` (default `data/budget.db` in the repo root).
- Tables: `member_budgets`, `usage_records`.

## Configuration

| Env | Meaning |
|-----|---------|
| `NEXA_BUDGET_ENABLED` | Master switch (default `true`). |
| `NEXA_BUDGET_DEFAULT_MONTHLY_LIMIT` | Default monthly token ceiling for new members (default `1000000`). |
| `NEXA_BUDGET_RESET_DAY` | Day-of-month anchor for period boundaries (1–28; default `1`). Period start is computed from this anchor so billing aligns across months. |

## Behavior

- **Monthly period**: On load paths (`check_and_reset_budget`), usage resets when crossing into a new period vs `last_reset` (see `app/services/budget/tracker.py`).
- **Warnings**: At ~80% and ~95% usage, warnings are logged once per period (`warning_sent_80` / `warning_sent_95` on the budget row).
- **Paused**: When usage reaches the monthly limit, status becomes **paused** and execution that respects budgets is blocked until usage is reduced or the limit is raised.
- **Manual adjustments**: `/budget adjust MemberName +50000` **grants headroom** by reducing recorded usage (positive delta). Negative deltas increase recorded usage (corrections).
- **Overrides**: `BudgetTracker.set_override(member_id, True)` sets status to **override** (bypass limits); usage rows may still be written for audit without incrementing the meter.

## Integration points

| Layer | Behavior |
|-------|----------|
| `primary_complete_messages` / `primary_complete_streaming` | Optional `budget_member_id` / `budget_member_name` kwargs charge the member after a successful LLM call (`app/services/llm/completion.py`). |
| `BudgetAwareLLMProvider` | Wraps any `LLMProvider` with the same gate + record semantics (`app/services/llm/budget_wrapper.py`). |
| `AgentExecutor.execute` | Pre-checks budget and records estimated tokens for agent tasks (`app/services/sub_agent_executor.py`). |

## Telegram

| Command | Purpose |
|---------|---------|
| `/budget` | Team summary. |
| `/budget MemberName` | One member’s meter and limits. |
| `/budget set MemberName <n>` | Set monthly token limit. |
| `/budget adjust MemberName +50000` | Grant headroom (positive) or add usage (negative). |
| `/timesheet` / `/workhours` | Recent usage rows (“timesheet”). |

Note: `/usage` is already used for **Nexa-wide LLM call statistics** (today/recent estimates). Use **`/timesheet`** for Phase 28 member usage history.

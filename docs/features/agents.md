# Agents

## Creating agents (natural language)

Examples:

- “Create a marketing agent”
- “Create a QA agent”
- “Create a developer agent”

## Creating agents (structured)

Examples:

- `create agent marketing_agent marketing`
- `create two agents qa_agent and marketing_agent`

Exact phrasing depends on channel and gateway routing — see [AGENTS.md](../AGENTS.md).

## Using agents

- `@marketing_agent create a tagline for FitAI`
- `@developer_agent add a delete button to the todo app`

## Listing agents

- `/subagent list` (Telegram and aligned surfaces)

## Domains (typical)

`marketing`, `qa`, `security`, `git`, `ops`, `test`, `dev`, `general` — see registry and templates in `app/services/` and [AGENTS.md](../AGENTS.md).

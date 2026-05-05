# Built-in plugin skills (Phase 6)

Skills that ship with Nexa use the same `skill.yaml` manifest format as community packages.
Place manifests under `data/nexa_skill_packages/` (Phase 53) or install via the plugin registry (`python -m nexa_cli skills install …`).

| Skill | Description | Example trigger |
| ----- | ----------- | --------------- |
| `git-commit-push` | Add README, commit, push | “add README and push” |
| `vercel-list` | List Vercel projects | “list vercel projects” |
| `vercel-remove` | Remove Vercel service | “stop service X” |
| `browser-scrape` | Scrape webpage | “scrape example.com” |
| `send-slack` | Send Slack message | “send slack to #channel” |

Many of these map to existing Nexa missions or gateway tools; manifests here document the OpenClaw-style packaging shape.

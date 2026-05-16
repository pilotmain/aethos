# Setup progress persistence

File: `~/.aethos/setup/setup_progress.json`

Tracks: current section, completed/skipped/failed sections, last prompt, runtime strategy, Mission Control seed status, onboarding profile status, repair recommendations.

CLI:

- `aethos setup status` — includes `setup_progress`
- `aethos setup resume` — resumes wizard from saved section
- `aethos setup repair` — repair install path

API: `GET /api/v1/setup/status` merges `setup_progress` from the same module.

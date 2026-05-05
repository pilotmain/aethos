# Phase 6 — Pluggable skills runtime

**Status:** Initial runtime (YAML manifests, in-memory registry, Python handlers, ClawHub HTTP client stub).  
**Coexists with:** Phase 22 user JSON skills (`app/services/skills/registry.py`, `/api/v1/skills`) and Phase 53 packaged manifests (`manifest_registry.py`).

## Layout

| Component | Path |
| --------- | ---- |
| Manifest loader | `app/services/skills/loader.py` (`SkillManifest`, `load_skill_manifest`) |
| Execution | `app/services/skills/executor.py` (`execute_python_skill`, shell stub) |
| Registry | `app/services/skills/plugin_registry.py` (`PluginSkillRegistry`, `get_plugin_skill_registry`) |
| Remote catalog | `app/services/skills/clawhub.py` + Phase 17 (`clawhub_client.py`, `installer.py`; see `docs/CLAWHUB_MARKETPLACE.md`) |
| Built-in table | `app/services/skills/builtin/README.md` |
| CLI | `python -m nexa_cli skills …` (`app/cli/skills.py`); marketplace: `nexa clawhub …` (`app/cli/clawhub.py`) |

## Configuration

| Env | Purpose |
| --- | ------- |
| `NEXA_CLAWHUB_API_BASE` | Base URL for ClawHub-compatible APIs (default `https://clawhub.com/api/v1`). |
| `NEXA_PLUGIN_SKILLS_ROOT` | Optional absolute path for installs; default `<repo>/data/nexa_plugin_skills`. |

## Manifest

Skills use a `skill.yaml` file with `name`, `version`, `execution.type` (`python` \| `shell`), `execution.entry`, `execution.handler`, optional `dependencies`, and JSON schemas. Installing from `file:///path/to/skill.yaml` parses the file, runs `pip install` for listed dependencies, and registers the skill in the process-local registry.

## Next steps (Phase 6.2)

- Embedding-based `discover_skill(task)`
- Shell execution with templating and permission gates

ClawHub ZIP download + unpack + local manifest are implemented in Phase 17 (`docs/CLAWHUB_MARKETPLACE.md`).

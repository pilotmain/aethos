# nexa-ext-pro

Optional **Pro** extension modules for [Nexa](https://github.com/pilotmain/nexa-next). Core OSS runs without this package; with a valid commercial license, Nexa activates stronger sandbox isolation, adaptive model routing, memory ranking, and broader auto-dev execution.

## Install

From PyPI (when published):

```bash
pip install nexa-ext-pro
```

From a checkout of `nexa-next` (editable):

```bash
pip install -e ./nexa-ext-pro
```

Set `NEXA_LICENSE_KEY` and `NEXA_LICENSE_PUBLIC_KEY_PEM` to a signed token whose `features` list includes the capability you need (see Nexa licensing docs).

## Modules

| Module | Feature flag | Role |
|--------|----------------|------|
| `nexa_ext.sandbox` | `sandbox_advanced` | Isolated execution (`docker` / `process`) |
| `nexa_ext.routing` | `smart_routing` | Task-aware Anthropic model selection |
| `nexa_ext.memory_intel` | `memory_intel` | Rerank retrieved memory entries |
| `nexa_ext.dev_execution` | `auto_dev` | More aggressive safe auto-dev policy |

## Core integration

The OSS core imports `nexa_ext.<name>` only when the package is installed **and** the license grants the matching feature. No extension / no license → built-in OSS behavior.

# Runtime strategy onboarding

| Strategy | Summary |
|----------|---------|
| **local-first** | Ollama primary; cloud fallback optional |
| **cloud-first** | API providers primary |
| **hybrid** | Intelligent routing with privacy-aware fallback |
| **configure-later** | Bootstrap first; providers deferred |

AethOS routes work to the best available reasoning engine. Change strategy later via `.env` or Mission Control.

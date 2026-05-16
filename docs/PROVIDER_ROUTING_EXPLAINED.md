# Provider routing explained

Providers are **interchangeable reasoning engines**. AethOS (the orchestrator) chooses routes; workers execute; providers reason.

- Advisory-first — recommendations require operator approval
- Automatic fallback when a provider is unavailable
- Examples: local Ollama, OpenAI, Anthropic, DeepSeek

**API:** `GET /api/v1/runtime/routing/explanations`

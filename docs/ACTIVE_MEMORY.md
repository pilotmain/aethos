# Active memory (Phase 15a)

Chunked **cosine recall** over filesystem memory (`MemoryStore` JSONL + markdown per entry). Embeddings use `embed_text_primary` (`app/services/memory/embedding.py`): deterministic pseudo-vectors by default, optional **Ollama** `/api/embeddings` when `NEXA_OLLAMA_EMBEDDINGS_ENABLED=true` and `NEXA_OLLAMA_ENABLED=true`.

## Flags

| Env | Default | Purpose |
| --- | ------- | ------- |
| `NEXA_ACTIVE_MEMORY_ENABLED` | `false` | Master switch. |
| `NEXA_ACTIVE_MEMORY_ALWAYS` | `false` | If `true`, runs chunk recall on **every** turn (still bounded by scan limits). If `false`, uses the same **follow-up cues** as the legacy semantic path (`from memory`, tech keywords, etc.). |
| `NEXA_ACTIVE_MEMORY_TOP_K` | `8` | Max hits returned. |
| `NEXA_ACTIVE_MEMORY_MIN_SCORE` | `0.12` | Minimum cosine similarity (tune when switching to real embeddings). |
| `NEXA_ACTIVE_MEMORY_MAX_CHARS` | `4000` | Cap on formatted injection block (reserved / formatting helper). |
| `NEXA_ACTIVE_MEMORY_CHUNK_CHARS` | `800` | Chunk size. |
| `NEXA_ACTIVE_MEMORY_CHUNK_OVERLAP` | `100` | Overlap between chunks. |
| `NEXA_ACTIVE_MEMORY_MAX_ENTRIES_SCAN` | `200` | Max entries read from the JSONL index per recall. |
| `NEXA_ACTIVE_MEMORY_INGEST_ENABLED` | `true` | Reserved for future auto-ingest hooks. |

## Gateway integration

`build_memory_context_for_turn` (`app/services/memory/context_injection.py`) merges chunk recall into `memory_context` when enabled. When hits apply, `GatewayContext.memory` includes `active_memory_used` and `active_memory_hits` (see `app/services/gateway/runtime.py` logs).

## REST API

`POST /api/v1/memory/recall` with header `Authorization: Bearer <NEXA_CRON_API_TOKEN>` (same automation token as cron / browser).

Body:

```json
{
  "query": "what database do we use?",
  "user_id": "<app user id>",
  "k": 8
}
```

Response: `{ "ok": true, "hits": [ ... ], "count": N }` — hit objects include `_similarity`, `entry_id`, `chunk_index`, `title`, `text`.

## Code references

- Chunking: `app/services/memory/chunking.py`
- Service: `app/services/memory/active_memory.py`
- `MemoryIndex.active_recall`: thin wrapper on the service

## Related paths

- Legacy JSON semantic ranking (whole-entry): `MemoryIndex.semantic_search`
- Web/agent preferences & DB notes: `/api/v1/web/memory/…`, `UserMemory`

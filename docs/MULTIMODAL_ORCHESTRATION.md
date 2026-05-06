# Phase 18 — Multi-modal (vision, audio, generation, uploads)

**Status:** Specification (implementation-ready).  
**Depends on:** Phase 11 (LLM providers / `Message`), Phase 12 (channels), Phase 14 (browser screenshots / base64 precedent), privacy/firewall stack.

This document defines goals, architecture, configuration, API shape, channel integration, limits, privacy, testing, and rollout order—aligned with existing code paths (`app/services/llm/*`, `safe_llm_gateway`, channel adapters, `audio_transcription.py` stub).

---

## 1. Objectives

| Goal | Description |
|------|-------------|
| **Vision** | Send images (and optionally video frames later) into the primary LLM path with provider-native vision models (GPT-4o / GPT-4V family, Claude 3+ vision, Gemini multimodal, Ollama llava/vision). |
| **Audio input** | Speech-to-text for user audio (voice notes, mic); inject transcript into the same gateway/chat pipeline as text. |
| **Audio output** | Optional text-to-speech for replies (channel-dependent; Telegram voice vs web audio blob). |
| **Image generation** | Optional create-image flows via OpenAI Images, Stability/Replicate, etc.—behind flags and budgets. |
| **Uploads** | Unified handling for **Telegram** (photo/document/voice), **Slack** (files shared in thread), and **HTTP API** (multipart)—normalize to internal **`MediaRef`** (see §4). |

Non-goals for v1:

- Real-time streaming duplex voice (WebRTC phone bridge).
- Arbitrary video understanding beyond still frames.

---

## 2. Architecture (high level)

```text
Channel (TG / Slack / Web API)
        │
        ▼
  Media ingest ──► Temp store / virus-scan hook (optional)
        │              │
        │              ▼
        │        Transcode caps (size, duration, pixels)
        │
        ▼
  Multimodal orchestrator (NEW: app/services/multimodal/*)
        │
        ├─► Vision ──► LLM provider w/ image parts (extend Phase 11)
        ├─► STT ─────► transcript string ──► gateway as text turn
        ├─► TTS ─────► audio bytes ──► channel send helper
        └─► Image gen ─► provider adapter ─► URL or bytes ─► channel / markdown embed
```

**Integration points (existing):**

- **`Message`** (`app/services/llm/base.py`) — today `content: str` only. Phase 18 introduces either:
  - **Option A (recommended):** `content: str | list[dict[str, Any]]` OpenAI-style blocks (`text` / `image_url` / `input_audio`), with providers translating; or
  - **Option B:** parallel field `attachments: list[MultimodalPart]` on a wrapper used only in multimodal routes until the stack is unified.
- **Providers** — `ModelInfo.supports_vision` already exists on Anthropic/OpenAI/Ollama backends; extend `complete_chat` signatures only where needed (internal helper to normalize multimodal user turns).
- **`safe_llm_gateway` / privacy** — vision/audio payloads must pass the same redaction / block-secret rules as text where applicable; images may need **optional** OCR/exif stripping policy (document in §7).
- **`audio_transcription.py`** — replace stubs with real providers behind flags (`NEXA_AUDIO_INPUT_ENABLED`, etc., §5).

---

## 3. Provider matrix (v1)

| Capability | Primary providers | Notes |
|------------|-------------------|--------|
| Vision | OpenAI (4o/4-turbo vision), Anthropic (Claude 3+), Google Gemini (if SDK integrated), Ollama (llava/vision) | Route by `nexa_multimodal_vision_provider` + model override. |
| STT | OpenAI Whisper API, optional Deepgram/Assembly | Start with one; unify interface `TranscriptionProvider.transcribe(path|bytes, mime) -> str`. |
| TTS | OpenAI TTS, optional ElevenLabs | Optional v1.1; Telegram sendVoice vs web download link. |
| Image gen | OpenAI `images/generations`, optional Stability/Replicate | Strict budget + approval alignment with token economy (Phase 38). |

All outbound calls must respect **`assert_provider_egress_allowed`** (see `app/services/llm/completion.py` pattern).

---

## 4. Internal contracts

### 4.1 `MediaRef` (conceptual)

```python
# Pseudocode — actual dataclass in app/services/multimodal/models.py
@dataclass
class MediaRef:
    kind: Literal["image", "audio", "video_frame"]
    mime: str
    bytes_or_path: Path | None  # temp file preferred for large audio
    source: Literal["telegram", "slack", "api", "internal"]
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    sha256: str | None = None  # dedupe / audit
```

### 4.2 Turn envelope extension

Channel handlers today pass normalized **text**. Extend normalized message structs (or parallel optional fields) with:

- `media: list[MediaRef]`
- `caption: str | None` (Telegram photo caption)

The gateway (`NexaGateway` / `handle_full_chat`) should receive either:

- **Transcript-first:** audio → STT → append caption + transcript as single `user` text for downstream intent routing, **or**
- **Parallel multimodal:** pass image + text into vision model without forcing STT for images.

---

## 5. Configuration (`app/core/config.py`)

Add flags (names illustrative—align with Pydantic `nexa_*` naming):

| Env | Default | Purpose |
|-----|---------|---------|
| `NEXA_MULTIMODAL_ENABLED` | `false` | Master kill switch. |
| `NEXA_MULTIMODAL_VISION_ENABLED` | `false` | Vision turns. |
| `NEXA_MULTIMODAL_VISION_PROVIDER` | `auto` | `auto` \| `openai` \| `anthropic` \| `gemini` \| `ollama` |
| `NEXA_MULTIMODAL_VISION_MODEL` | _(optional)_ | Override model for vision turns. |
| `NEXA_AUDIO_INPUT_ENABLED` | `false` | STT path on supported channels. |
| `NEXA_AUDIO_TRANSCRIPTION_PROVIDER` | `openai` | e.g. whisper-compatible endpoint. |
| `NEXA_AUDIO_OUTPUT_ENABLED` | `false` | TTS for outbound (optional). |
| `NEXA_IMAGE_GEN_ENABLED` | `false` | Image generation tools/routes. |
| `NEXA_IMAGE_GEN_PROVIDER` | `openai` | Provider key for generations. |
| `NEXA_MULTIMODAL_MAX_IMAGE_BYTES` | `10485760` | 10 MB default cap per image. |
| `NEXA_MULTIMODAL_MAX_AUDIO_SECONDS` | `300` | Cap voice note duration. |
| `NEXA_MULTIMODAL_MAX_IMAGE_SIDE_PX` | `8192` | Downscale policy hook. |
| `NEXA_MULTIMEDIA_TEMP_TTL_SECONDS` | `3600` | Temp file cleanup. |

Sync **`.env.example`** and **`.env`** per repo env-sync rules.

---

## 6. REST API shape (Mission Control / web)

Auth follows existing patterns:

- **User-scoped:** `get_valid_web_user_id` (`X-User-Id` + optional web bearer)—for browser uploads from Next.js.
- **Automation-scoped:** optional separate internal routes with cron token **only** if needed; default public product path is web auth.

Suggested routes (prefix `/api/v1/multimodal`):

| Method | Path | Body | Response |
|--------|------|------|----------|
| `POST` | `/vision/analyze` | `multipart/form-data`: `image`, optional `prompt`, optional `session_id` | `{ "ok", "text", "model", "usage" }` |
| `POST` | `/audio/transcribe` | `multipart`: `audio` | `{ "ok", "text", "language" }` |
| `POST` | `/speech/synthesize` | JSON `{ "text", "voice" }` *(if TTS)* | `{ "ok", "audio_url" \| "audio_base64" }` |
| `POST` | `/image/generate` | JSON `{ "prompt", "size", "n" }` | `{ "ok", "urls" \| "b64_json" }` |

All gated by §5 flags; return **503** when disabled with stable `code` string.

---

## 7. Privacy, safety, limits

- **Ingress:** reject unknown MIME types; strip EXIF on outbound vision upload to third parties if policy flag `NEXA_MULTIMODAL_STRIP_IMAGE_METADATA=true`.
- **Content:** reuse PII redaction where transcript is merged into LLM context (`nexa_redact_pii_before_external_api` etc.).
- **Storage:** temp files under `data/multimedia/tmp/` (new) or `nexa_workspace`-scoped; never log raw base64 in INFO logs (structured `nexa_event` + lengths/hashes only).
- **Budget:** tie image-gen and heavy vision to existing token/cost budgets (`nexa_token_budget_*`, `nexa_cost_budget_*`) where applicable; add per-day image-gen counter if needed.
- **Approvals:** optional `waiting_approval` for image-gen jobs when `nexa_approvals_enabled`—align with governance docs.

---

## 8. Channel integration

### 8.1 Telegram

- **Photo:** download file → `MediaRef(kind=image)` → vision or caption+vision.
- **Voice:** `transcribe_telegram_voice` implementation using Bot API `getFile` → STT → inject as user message.
- **Document** (image/pdf): v1 images only; PDF optional “extract page 1 raster” later.

### 8.2 Slack

- File shared events: resolve download URL with bot token → same `MediaRef` pipeline.
- Respect `nexa_slack_route_inbound` / gateway path consistency.

### 8.3 Web / API

- Multipart upload endpoints (§6); CORS already configured for local Next dev.

---

## 9. Testing strategy

| Layer | Tests |
|-------|--------|
| Unit | MIME validation, size caps, EXIF strip (if implemented), `MediaRef` serialization. |
| Provider mocks | httpx mock for OpenAI vision/transcribe/generate responses. |
| Integration | `TestClient` multipart → stub provider → assert JSON schema; gate disabled → 503. |
| Channel smoke | Optional: pytest with Telegram/Slack fixtures if present; else manual checklist. |

Add **`tests/test_multimodal*.py`**; keep tests hermetic (no real API keys).

---

## 10. Documentation deliverables

| File | Purpose |
|------|---------|
| `docs/MULTIMODAL_ORCHESTRATION.md` | This spec (operator + implementer). |
| Update `docs/SKILLS_SYSTEM.md` / gateway docs only if multimodal hooks surface new tools—otherwise avoid scope creep. |

---

## 11. Rollout phases (implementation order)

1. **18a — Models + config + ingest utilities** (`MediaRef`, temp store, flags, `.env.example`). **✅ Landed:** `app/services/multimodal/*`, `app/api/routes/multimodal.py`, Settings keys in `app/core/config.py`, tests `tests/test_multimodal_phase18a.py`.
2. **18b — Extend LLM `Message` / provider adapters** for a single vision path (OpenAI or Anthropic first).
3. **18c — REST `/multimodal/vision/analyze` + tests.**
4. **18d — STT (implement `audio_transcription.py`) + Telegram voice → text pipeline.**
5. **18e — Image generation** (flagged, budgeted).
6. **18f — TTS + Slack file polish** (optional).

---

## 12. Open decisions (resolve before coding)

1. **Gemini** — add Google SDK vs HTTP-only; placement in provider registry.
2. **PDF** — in scope for 18 or defer to 18.2?
3. **User retention** — whether to persist uploaded media beyond temp (audit vs privacy).

---

## 13. One-liner for implementation

Implement Phase 18 per `docs/MULTIMODAL_ORCHESTRATION.md`: multimodal orchestration module, extend LLM messages/providers for vision, STT/TTS adapters, optional image generation, Telegram/Slack/API upload normalization, config flags, `/api/v1/multimodal/*` routes with Mission Control auth where appropriate, privacy limits, tests, and env/docs sync.

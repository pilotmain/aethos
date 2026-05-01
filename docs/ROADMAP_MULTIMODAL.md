# Nexa multimodal roadmap (product order)

Nexa grows in layers. **Text and documents** stay primary; other modalities are additive.

## 1. Text and documents (current)

- Chat, memory, research, custom agents, plans.
- Exports: PDF, DOCX, Markdown, text; user-scoped storage under `.runtime/generated_documents/`.

## 2. Audio input (next candidate)

- **Telegram**: voice note → download file → **transcribe** → run the same message pipeline as typed text.
- **Web** (optional): **microphone** near composer; show transcription in the composer; user can edit before send.
- **Providers (examples)**: OpenAI Whisper API, local Whisper, Deepgram, etc.
- **Principles**: user-owned audio; no background recording; delete temp files after transcription unless the user opts in; same safety rules as text.

## 3. Audio output (later, optional)

- **TTS** for replies: briefings, summaries, accessibility.
- Stays **optional**; text remains the default and source of truth.

## 4. Video understanding (later)

- **Upload** a video file; **extract audio**; transcribe; optionally **sample frames**; summarize.
- **Use cases**: meeting recordings, demos, short screen captures, extracting tasks.
- **Tools (examples)**: `ffmpeg`, transcription API, optional vision for frames later.
- **Principles**: user-uploaded input only; no private URLs; delete temps; no hidden capture.

## 5. Video generation (lowest priority)

- Not a near-term product goal. If it ever exists, it should be **provider-based** and **explicit** user action.

**Rule of thumb:** Text and documents first → audio in → audio out (optional) → video understanding last → **video generation last, if ever**.

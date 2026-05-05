"""Phase 18 — multi-modal services (18a: config + skeleton; providers in 18b+)."""

from app.services.multimodal.models import MediaKind, MediaRef, MultimodalPhase18APlaceholder
from app.services.multimodal.orchestrator import (
    analyze_image_stub,
    audio_input_enabled,
    audio_output_enabled,
    generate_image_stub,
    image_gen_enabled,
    max_image_bytes_cap,
    multimodal_globally_enabled,
    synthesize_speech_stub,
    transcribe_audio_stub,
    vision_enabled,
)

__all__ = [
    "MediaKind",
    "MediaRef",
    "MultimodalPhase18APlaceholder",
    "analyze_image_stub",
    "audio_input_enabled",
    "audio_output_enabled",
    "generate_image_stub",
    "image_gen_enabled",
    "max_image_bytes_cap",
    "multimodal_globally_enabled",
    "synthesize_speech_stub",
    "transcribe_audio_stub",
    "vision_enabled",
]

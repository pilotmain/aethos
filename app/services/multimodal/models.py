"""Phase 18 — multimodal DTOs (ingest + orchestration)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal


class MediaKind(str, Enum):
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO_FRAME = "video_frame"


@dataclass
class MediaRef:
    """User or channel-originated media (normalized before provider calls)."""

    kind: MediaKind
    mime: str
    source: Literal["telegram", "slack", "api", "internal"]
    bytes_or_path: Path | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    sha256: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        p = self.bytes_or_path
        return {
            "kind": self.kind.value,
            "mime": self.mime,
            "source": self.source,
            "path": str(p) if p is not None else None,
            "width": self.width,
            "height": self.height,
            "duration_s": self.duration_s,
            "sha256": self.sha256,
        }


class MultimodalPhase18APlaceholder(Exception):
    """Raised when Phase 18a skeleton is hit before provider integration (18b+)."""

    code: str = "PHASE_18A_PLACEHOLDER"

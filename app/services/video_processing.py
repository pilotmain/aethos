# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

# Future: user-uploaded video — extract audio, transcribe, optional frame samples (ffmpeg + provider).
# Not part of the document export milestone. Do not download private URLs without explicit user file.

from __future__ import annotations

from pathlib import Path


def extract_audio_from_video(path: Path) -> Path:  # pragma: no cover
    raise NotImplementedError("Video processing is not enabled yet.")


def transcribe_video(path: Path, user_id: str) -> str:  # pragma: no cover
    raise NotImplementedError("Video processing is not enabled yet.")

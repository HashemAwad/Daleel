"""Voice-note transcription (B4). Owner: B.

`TranscriberImpl.transcribe(audio, mime) -> (text, lang)` using local faster-whisper
(no network call at inference, so audio never leaves the machine). WhatsApp voice notes
are ogg/opus; PyAV (bundled with faster-whisper) decodes them, no ffmpeg needed.

Config (env): WHISPER_MODEL (default "small"; use "medium"/"large-v3" for better Arabic),
WHISPER_DEVICE (default "auto"), WHISPER_COMPUTE (default "int8").
Never log audio, transcripts, or exception messages from here.
"""
from __future__ import annotations

import io
import os
from typing import Any, Optional

from shared.contracts import Lang

_SUPPORTED = {"ar", "fr", "en"}          # Whisper codes we map straight onto Lang
_FALLBACK = "ar"                          # Lebanese audio mis-detected as fa/ur/etc. -> retry as Arabic


class TranscriberImpl:
    def __init__(self, model: Any = None):
        self._model = model               # injectable for tests; loaded lazily otherwise

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                os.getenv("WHISPER_MODEL", "small"),
                device=os.getenv("WHISPER_DEVICE", "auto"),
                compute_type=os.getenv("WHISPER_COMPUTE", "int8"))
        return self._model

    def _run(self, audio: bytes, language: Optional[str]):
        segments, info = self._load().transcribe(
            io.BytesIO(audio), language=language, vad_filter=True, beam_size=5)
        text = " ".join(s.text.strip() for s in segments).strip()   # generator: consume it
        return text, info.language

    def transcribe(self, audio: bytes, mime: str = "") -> tuple[str, Optional[Lang]]:
        """`mime` is accepted for the contract; PyAV sniffs the container itself."""
        if not audio:
            return "", None
        text, code = self._run(audio, None)
        if code not in _SUPPORTED:
            text, code = self._run(audio, _FALLBACK)
        return text, code if code in _SUPPORTED else None

"""Voice-note transcription (B4). Owner: B.

`TranscriberImpl.transcribe(audio, mime) -> (text, lang)` using local faster-whisper
(no network call at inference, so audio never leaves the machine). WhatsApp voice notes
are ogg/opus; PyAV (bundled with faster-whisper) decodes them in memory, no ffmpeg and
no temp file.

Config (env): WHISPER_MODEL (default "small"; use "medium"/"large-v3" for better Arabic),
WHISPER_DEVICE (default "auto"), WHISPER_COMPUTE (default "int8"),
WHISPER_MAX_SECONDS (default 60: only the first minute of a long note is transcribed).
Never log audio, transcripts, or exception messages from here.

Try a file by hand:  PYTHONPATH=src python -m ai.transcribe clip.ogg [--answer]
"""
from __future__ import annotations

import io
import logging
import os
import threading
from typing import Any, Optional

from shared.contracts import Lang

log = logging.getLogger("daleel.ai.transcribe")

# Whisper codes we map straight onto Lang. Arabic first: Lebanese audio mis-detected as
# fa/ur/he falls back to the likeliest of these three, and to Arabic on a tie.
_SUPPORTED = ("ar", "fr", "en")


def _max_seconds() -> float:
    return float(os.getenv("WHISPER_MAX_SECONDS", "60"))


class TranscriberImpl:
    def __init__(self, model: Any = None):
        self._model = model               # injectable for tests; loaded lazily otherwise
        self._lock = threading.Lock()

    def _load(self, local_only: bool = False):
        """`local_only` is what the running app uses: a model that was never downloaded must
        fail at once, not start a 500 MB+ download in the middle of a webhook."""
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    os.getenv("WHISPER_MODEL", "small"),
                    device=os.getenv("WHISPER_DEVICE", "auto"),
                    compute_type=os.getenv("WHISPER_COMPUTE", "int8"),
                    local_files_only=local_only)
        return self._model

    def ready(self) -> bool:
        """Load the model now. False plus one ERROR line when it cannot load, so a missing
        model is seen at startup and in /health/channels, not as "couldn't read" replies."""
        try:
            self._load(local_only=True)
            return True
        except Exception as exc:
            log.error("Whisper model %r did not load (%s): voice notes will NOT work. Run "
                      "infra/laptop_setup.sh on a good connection.",
                      os.getenv("WHISPER_MODEL", "small"), type(exc).__name__)
            return False

    def _run(self, audio: bytes, language: Optional[str]):
        """Returns (lazy segments, info): language detection has run, decoding has not."""
        return self._load(local_only=True).transcribe(
            io.BytesIO(audio), language=language, vad_filter=True, beam_size=5)

    def transcribe(self, audio: bytes, mime: str = "") -> tuple[str, Optional[Lang]]:
        """`mime` is accepted for the contract; PyAV sniffs the container itself.
        Raises on undecodable audio or a model that cannot load; callers reply "couldn't read"."""
        if not audio:
            return "", None
        segments, info = self._run(audio, None)
        code = info.language
        if code not in _SUPPORTED:
            # decide before decoding anything, so a wrong guess costs one detection, not a full pass
            probs = dict(getattr(info, "all_language_probs", None) or ())
            code = max(_SUPPORTED, key=lambda c: probs.get(c, 0.0))
            segments, info = self._run(audio, code)
        parts, limit = [], _max_seconds()
        for s in segments:                                 # lazy: stopping here stops the work
            if getattr(s, "start", 0.0) >= limit:
                break
            parts.append(s.text.strip())
        return " ".join(parts).strip(), code


def _main(argv=None) -> int:
    """Test one audio file by hand. Prints to the terminal only: nothing is stored or logged.
        PYTHONPATH=src python -m ai.transcribe clip.ogg            transcript + language + seconds
        PYTHONPATH=src python -m ai.transcribe clip.ogg --answer   also run the pipeline, print the reply
    """
    import argparse
    import time
    from pathlib import Path
    p = argparse.ArgumentParser(prog="python -m ai.transcribe", description=_main.__doc__.splitlines()[0])
    p.add_argument("file")
    p.add_argument("--answer", action="store_true", help="also run the pipeline and print the reply")
    args = p.parse_args(argv)

    audio = Path(args.file).read_bytes()
    t = TranscriberImpl()
    t0 = time.perf_counter()
    t._load()
    t1 = time.perf_counter()
    text, lang = t.transcribe(audio, "")
    t2 = time.perf_counter()
    print(f"model:      {os.getenv('WHISPER_MODEL', 'small')} (loaded in {t1 - t0:.1f}s)")
    print(f"transcript: {text!r}")
    print(f"language:   {lang}")
    print(f"seconds:    {t2 - t1:.1f}")
    if args.answer:
        os.environ["RECORD_TURNS"] = "0"                  # a hand test must not write a turn to the DB
        from core import pipeline
        from shared.contracts import Inquiry
        a = pipeline.handle(Inquiry(id="cli", channel="whatsapp", text=text, lang=lang, user_ref="cli"))
        print(f"tool:       {a.tool}   outcome: {a.outcome}   ({time.perf_counter() - t2:.1f}s)")
        print(f"reply:\n{a.text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

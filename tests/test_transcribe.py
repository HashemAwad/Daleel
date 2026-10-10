"""B4: TranscriberImpl with a fake Whisper model (no download). A real-audio test runs only
with VOICE_REAL=1 and a fixture: tests/fixtures/ar_sample.ogg + ar_sample.txt (expected substring).
More voice tests (failures, time budget, privacy): tests/test_voice.py."""
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from ai.transcribe import TranscriberImpl

FIX = Path(__file__).parent / "fixtures"


class FakeModel:
    def __init__(self, detected, texts=("مرحبا", "كيف الحال")):
        self.detected, self.texts, self.calls = detected, texts, []

    def transcribe(self, audio, language=None, **kw):
        self.calls.append(language)
        lang = language or self.detected
        return (SimpleNamespace(text=f" {t} ") for t in self.texts), SimpleNamespace(language=lang)


def test_joins_segments_and_maps_lang():
    t = TranscriberImpl(FakeModel("ar"))
    assert t.transcribe(b"x", "audio/ogg") == ("مرحبا كيف الحال", "ar")


@pytest.mark.parametrize("code", ["fr", "en"])
def test_supported_langs(code):
    assert TranscriberImpl(FakeModel(code)).transcribe(b"x", "audio/ogg")[1] == code


def test_unsupported_detection_retries_as_arabic():
    m = FakeModel("fa")
    text, lang = TranscriberImpl(m).transcribe(b"x", "audio/ogg")
    assert m.calls == [None, "ar"] and lang == "ar" and text


def test_empty_audio_skips_model():
    m = FakeModel("ar")
    assert TranscriberImpl(m).transcribe(b"", "audio/ogg") == ("", None)
    assert m.calls == []


@pytest.mark.skipif(os.getenv("VOICE_REAL") != "1" or not (FIX / "ar_sample.ogg").exists(),
                    reason="needs VOICE_REAL=1 and an audio fixture")
def test_real_arabic_clip():
    text, lang = TranscriberImpl().transcribe((FIX / "ar_sample.ogg").read_bytes(), "audio/ogg")
    assert lang == "ar" and (FIX / "ar_sample.txt").read_text(encoding="utf-8").strip() in text

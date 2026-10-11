"""Voice notes end to end, with no model and no network: failure cases, the webhook time budget,
and privacy. A fake Whisper model / fake transcriber stands in everywhere.

Real-model tests run only when asked:
    VOICE_REAL=1 VOICE_CLIPS_DIR=/path/to/clips PYTHONPATH=src pytest -q tests/test_voice.py
Each clip may have a sibling <name>.txt: one acceptable substring per line (any one must appear).
"""
import io
import logging
import os
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from ai import transcribe as tr
from ai.transcribe import TranscriberImpl
from channels import whatsapp
from channels.asgi import app
from channels.settings_extra import channel_settings
from core import pipeline, providers, stubs
from data import transcripts
from shared.config import settings

client = TestClient(app)
PHONE = "whatsapp:+96170123456"
SPOKEN_PII = "my name is John Smith and my number is 03 123 456, how much is concor 5"


def voice_form(**over) -> dict:
    base = {"From": PHONE, "To": "whatsapp:+14155238886", "Body": "", "MessageSid": "SM1",
            "AccountSid": "AC123", "NumMedia": "1", "MediaUrl0": "https://api.twilio.com/media/ME1",
            "MediaContentType0": "audio/ogg"}
    base.update(over)
    return base


def hears(text, lang="en"):
    return type("T", (), {"transcribe": lambda self, audio, mime="": (text, lang), "ready": lambda self: True})()


class RecordingLLM:
    """Not a StubLLM: the pipeline skips the model call for the stub."""
    def __init__(self):
        self.seen = []

    def classify(self, text, labels):
        self.seen.append(text)
        return labels[0]

    def generate(self, system, prompt, context=""):
        self.seen.append(prompt + context)
        return "ok"


@pytest.fixture(autouse=True)
def _channel(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(channel_settings, "require_twilio_signature", False)
    monkeypatch.setattr(providers, "procedures", stubs.StubProcedureSearch())
    monkeypatch.setattr(providers, "medicine", stubs.StubMedicine())
    monkeypatch.setattr(whatsapp, "fetch_media", lambda url, form: b"\x00AUDIO-BYTES-MARKER\x00")


# ---- ai.transcribe with a fake model ---------------------------------------
class FakeWhisper:
    """Mimics faster-whisper: detection is eager, segments are a lazy generator."""
    def __init__(self, detected="ar", probs=(), starts=(0.0,)):
        self.detected, self.probs, self.starts = detected, probs, starts
        self.calls, self.decoded, self.audio_types = [], [], []

    def transcribe(self, audio, language=None, **kw):
        self.calls.append(language)
        self.audio_types.append(type(audio))

        def segments():
            for start in self.starts:
                self.decoded.append((language, start))
                yield SimpleNamespace(text=f" s{start:g} ", start=start)
        return segments(), SimpleNamespace(language=language or self.detected, all_language_probs=list(self.probs))


def test_misdetected_language_falls_back_to_likeliest_supported_without_a_wasted_pass():
    m = FakeWhisper("es", probs=[("es", 0.5), ("fr", 0.3), ("ar", 0.1), ("en", 0.05)])
    text, lang = TranscriberImpl(m).transcribe(b"x")
    assert lang == "fr" and m.calls == [None, "fr"] and text
    assert all(language == "fr" for language, _ in m.decoded)      # the first pass was never decoded


def test_misdetection_with_no_probabilities_falls_back_to_arabic():
    assert TranscriberImpl(FakeWhisper("fa")).transcribe(b"x")[1] == "ar"


def test_long_note_stops_at_the_cap(monkeypatch):
    monkeypatch.setenv("WHISPER_MAX_SECONDS", "60")
    m = FakeWhisper(starts=(0.0, 28.0, 55.0, 61.0, 90.0, 120.0))
    text, _ = TranscriberImpl(m).transcribe(b"x")
    assert text == "s0 s28 s55"
    assert [start for _, start in m.decoded] == [0.0, 28.0, 55.0, 61.0]   # nothing past the cap was computed


def test_audio_reaches_the_model_in_memory_only():
    m = FakeWhisper()
    TranscriberImpl(m).transcribe(b"x")
    assert m.audio_types == [io.BytesIO]                              # not a path: no temp file


def test_whisper_is_given_the_vocabulary_hints(monkeypatch):
    seen = {}

    class M(FakeWhisper):
        def transcribe(self, audio, language=None, **kw):
            seen.update(kw)
            return super().transcribe(audio, language, **kw)
    TranscriberImpl(M()).transcribe(b"x")
    assert "Aley" in seen["hotwords"] and "عاليه" in seen["hotwords"] and "Concor" in seen["hotwords"]
    monkeypatch.setenv("WHISPER_HINTS", "Hamra")
    TranscriberImpl(M()).transcribe(b"x")
    assert seen["hotwords"] == "Hamra"


def _broken_whisper(monkeypatch, seen):
    def boom(*args, **kwargs):
        seen.append(kwargs)
        raise RuntimeError("model.bin is missing")
    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=boom))


def test_missing_model_is_loud_and_never_downloads_at_runtime(monkeypatch, caplog):
    seen = []
    _broken_whisper(monkeypatch, seen)
    t = TranscriberImpl()
    with caplog.at_level(logging.ERROR):
        assert t.ready() is False
    assert "voice notes will NOT work" in caplog.text and "model.bin" not in caplog.text
    with pytest.raises(RuntimeError):                                  # raises: no silent empty transcript
        t.transcribe(b"x")
    assert seen and all(kw["local_files_only"] is True for kw in seen)


def test_app_wiring_uses_the_real_transcriber_not_the_stub(_hermetic_transcriber):
    assert type(_hermetic_transcriber).__name__ == "TranscriberImpl"


def test_health_reports_a_model_that_cannot_load(monkeypatch):
    _broken_whisper(monkeypatch, [])
    monkeypatch.setattr(providers, "transcriber", TranscriberImpl())
    body = client.get("/health/channels").json()
    assert body["providers"]["transcriber"] == "TranscriberImpl" and body["voice_ready"] is False


# ---- failure cases: always a clear reply, never a 500 or silence ------------
def _raises(exc):
    def transcribe(self, audio, mime=""):
        raise exc
    return type("T", (), {"transcribe": transcribe})()


@pytest.mark.parametrize("transcriber", [
    hears("", None),                                    # empty file / silence / VAD removed everything
    hears("   ", "ar"),
    _raises(ValueError("Invalid data found when processing input")),   # corrupt, non-audio, amr
    _raises(RuntimeError("model.bin is missing")),      # model not on disk
], ids=["empty", "blank", "undecodable", "no-model"])
def test_unusable_voice_note_gets_the_cannot_read_reply(monkeypatch, transcriber):
    monkeypatch.setattr(providers, "transcriber", transcriber)
    r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert r.status_code == 200 and "couldn't read" in r.text and "1787" in r.text


def test_gibberish_transcript_still_gets_a_reply(monkeypatch):
    monkeypatch.setattr(providers, "transcriber", hears("شكرا ترجمة نانسي قنقر", "ar"))
    monkeypatch.setattr(providers, "procedures", type("P", (), {"search": lambda *a, **k: []})())
    r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert r.status_code == 200 and "1787" in r.text


def test_a_crash_in_the_turn_is_a_reply_not_a_500(monkeypatch):
    monkeypatch.setattr(whatsapp.pipeline, "handle", lambda inq: 1 / 0)
    r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert r.status_code == 200 and "1787" in r.text


# ---- Twilio's 15 seconds ----------------------------------------------------
def _slow_pipeline(monkeypatch, seconds=0.4):
    real = pipeline.handle

    def slow(inq):
        time.sleep(seconds)
        return real(inq)
    monkeypatch.setattr(whatsapp.pipeline, "handle", slow)
    monkeypatch.setattr(whatsapp, "REPLY_BUDGET_SECONDS", 0.05)
    monkeypatch.setattr(providers, "transcriber", hears("my father is not breathing"))


def test_over_budget_without_rest_credentials_says_so(monkeypatch):
    _slow_pipeline(monkeypatch)
    r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert r.status_code == 200 and "took too long" in r.text


def test_over_budget_with_rest_credentials_sends_the_answer_afterwards(monkeypatch):
    from twilio.request_validator import RequestValidator
    _slow_pipeline(monkeypatch)
    monkeypatch.setattr(settings, "twilio_auth_token", "tok")
    sent = []
    monkeypatch.setattr(whatsapp, "_send_later", lambda form, parts: sent.append((form["From"], parts)))
    payload = voice_form()
    sig = RequestValidator("tok").compute_signature("http://testserver" + whatsapp.WEBHOOK_PATH, payload)
    r = client.post(whatsapp.WEBHOOK_PATH, data=payload, headers={"X-Twilio-Signature": sig})
    assert r.status_code == 200 and "on its way" in r.text
    deadline = time.monotonic() + 3
    while not sent and time.monotonic() < deadline:
        time.sleep(0.02)
    assert len(sent) == 1 and sent[0][0] == PHONE and "140" in sent[0][1][0]


def test_in_budget_reply_is_not_sent_twice(monkeypatch):
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    monkeypatch.setattr(providers, "transcriber", hears("my father is not breathing"))
    monkeypatch.setattr(whatsapp, "_send_later", lambda form, parts: pytest.fail("must not send twice"))
    assert "140" in client.post(whatsapp.WEBHOOK_PATH, data=voice_form()).text


# ---- privacy ----------------------------------------------------------------
def test_spoken_phone_and_name_are_redacted_before_the_model_and_never_logged(monkeypatch, caplog):
    llm = RecordingLLM()
    monkeypatch.setattr(providers, "llm", llm)
    # Use a PROCEDURE question: directory/medicine answers are rendered directly
    # (no model), so a procedure is the path that actually reaches the model —
    # which is what lets us check the prompt was redacted first.
    pii = "my name is John Smith and my number is 03 123 456, how do I renew my prescription?"
    monkeypatch.setattr(providers, "transcriber", hears(pii))
    from shared.contracts import Doc
    monkeypatch.setattr(providers, "procedures",
                        type("P", (), {"search": lambda self, q, lang=None, k=4:
                                       [Doc(id="1", title="Renewal", content="Bring your ID.")]})())
    with caplog.at_level(logging.DEBUG):
        r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert r.status_code == 200 and llm.seen, "the model was never reached, so this test proved nothing"
    for prompt in llm.seen:
        assert "John" not in prompt and "Smith" not in prompt and "123" not in prompt
        assert "[NAME]" in prompt and "[PHONE]" in prompt
    for secret in ("John", "Smith", "123 456", "70123456", "AUDIO-BYTES-MARKER"):
        assert secret not in caplog.text


@pytest.mark.parametrize("heard", [
    "اسميها شمعوال ورقم صفرتلاتة، مية وثلاتة وعشرين، أربع مية وستة وخمسين، وين أقرب صيدالية بعالي؟",   # real Whisper output
    "رقمي صفر تلاتة تمانية خمسة ستة واحد تنين",
    "my number is zero three one two three four five six",
    "mon numéro est zéro trois, cent vingt-trois, quatre cent cinquante-six",
])
def test_a_phone_number_spoken_as_words_is_masked(heard):
    out = providers.redact(heard)
    assert "[PHONE]" in out
    for word in ("صفر", "مية", "وعشرين", "وخمسين", "تمانية", "three", "cent", "vingt"):
        assert word not in out


def test_a_name_with_diacritics_is_masked_whole():
    out = providers.redact("اسمي هاشي معوّاد ورقمي 0-3-123-456 وين أقرب صيدلية بعليه؟")   # real Whisper output
    assert "هاشي" not in out and "اد" not in out.replace("[", " ").split() and "123" not in out and "صيدلية" in out


@pytest.mark.parametrize("heard", ["قديش سعر كونكور خمسة", "how much is concor five", "one or two pharmacies in Aley",
                                   "بدي خمسة وعشرين حبة", "le prix du concor cinq", "وين أقرب صيدلية بعاليه"])
def test_a_strength_or_a_small_count_is_not_mistaken_for_a_phone_number(heard):
    assert providers.redact(heard) == heard


def test_emergency_voice_note_gets_140_and_stores_no_text(monkeypatch):
    llm, recorded = RecordingLLM(), []
    monkeypatch.setattr(providers, "llm", llm)
    monkeypatch.setattr(providers, "transcriber", hears("my name is John, my father is not breathing"))
    monkeypatch.setattr(pipeline.transcripts, "record", lambda inq, ans: recorded.append((inq, ans)))
    monkeypatch.setenv("STORE_TRANSCRIPT_TEXT", "1")
    r = client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    assert "140" in r.text and llm.seen == []                          # no model call on an emergency
    (inq, ans), = recorded
    assert ans.outcome == "emergency"
    assert transcripts._storable(inq.text, ans) == transcripts.NO_TEXT
    assert transcripts._storable(ans.text, ans) == transcripts.NO_TEXT
    assert inq.user_ref.startswith("wa_") and "70123456" not in inq.user_ref


def test_a_voice_turn_stores_only_scrubbed_text(monkeypatch):
    """A voice transcript is stored exactly like typed text: masked, and only with STORE_TRANSCRIPT_TEXT=1."""
    recorded = []
    monkeypatch.setattr(providers, "transcriber", hears(SPOKEN_PII))
    monkeypatch.setattr(pipeline.transcripts, "record", lambda inq, ans: recorded.append((inq, ans)))
    client.post(whatsapp.WEBHOOK_PATH, data=voice_form())
    (inq, ans), = recorded
    monkeypatch.setenv("STORE_TRANSCRIPT_TEXT", "1")
    stored = transcripts._storable(inq.text, ans)
    assert "concor" in stored and "John" not in stored and "123" not in stored
    monkeypatch.delenv("STORE_TRANSCRIPT_TEXT")
    assert transcripts._storable(inq.text, ans) == transcripts.NO_TEXT


# ---- real model, only when asked --------------------------------------------
AUDIO = {".ogg", ".opus", ".mp3", ".m4a", ".wav"}
CLIPS = sorted(p for p in Path(os.getenv("VOICE_CLIPS_DIR", "/nonexistent")).glob("*") if p.suffix in AUDIO)


@pytest.mark.skipif(os.getenv("VOICE_REAL") != "1", reason="set VOICE_REAL=1 (loads the real Whisper model)")
@pytest.mark.parametrize("clip", CLIPS, ids=lambda p: p.name)
def test_real_clip(clip, _hermetic_transcriber):
    before = set(os.listdir(tempfile.gettempdir()))
    text, lang = _hermetic_transcriber.transcribe(clip.read_bytes(), "")
    assert set(os.listdir(tempfile.gettempdir())) <= before, "transcription left a temp file"
    assert text and lang in tr._SUPPORTED
    expected = clip.with_suffix(".txt")
    if expected.exists():
        wanted = [line.strip() for line in expected.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert any(w in text for w in wanted), f"none of {wanted} in transcript"

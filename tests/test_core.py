"""Dev A core tests: routing, safety (multilingual), grounding gate, voice path."""
import pytest
from shared.contracts import Inquiry, ToolResult
from core import pipeline, router


def _inq(text="", audio_url=None, lang=None):
    return Inquiry(id="t", channel="web", text=text, user_ref="t", audio_url=audio_url, lang=lang)


# ---- A4: routing picks the right tool -------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("how do I get my cancer medicine from the ministry?", "procedure"),
    ("nearest pharmacy in Aley", "directory"),
    ("أقرب مستشفى", "directory"),
    ("combien coûte le Concor 5?", "medicine"),
    ("سعر الدوا", "medicine"),
])
def test_keyword_router_picks_tool(text, expected):
    # Test the deterministic keyword rules directly. route() may defer to the
    # model when one is installed (covered separately in the model-routing tests),
    # so asserting on route() here would depend on the environment.
    assert router.route_keywords(_inq(text)) == expected


# ---- A4: model-driven routing overrides keywords when a real model exists --
def test_model_routing_overrides_keywords(monkeypatch):
    class FakeLLM:  # not a StubLLM -> model path is used
        def classify(self, text, labels):
            return "directory"
        def generate(self, system, prompt, context=""):
            return "ok"
        def embed(self, texts):
            return []
    monkeypatch.setenv("MODEL_ROUTER", "1")  # model routing is opt-in
    monkeypatch.setattr(router.providers, "llm", FakeLLM())
    # text has no directory keywords, but the model says "directory"
    assert router.choose_tool(_inq("I want to find a place")) == "directory"


def test_model_routing_falls_back_on_error(monkeypatch):
    class BoomLLM:
        def classify(self, text, labels):
            raise RuntimeError("model down")
        def generate(self, system, prompt, context=""):
            return "ok"
        def embed(self, texts):
            return []
    monkeypatch.setattr(router.providers, "llm", BoomLLM())
    assert router.choose_tool(_inq("nearest pharmacy")) == "directory"  # keyword fallback


# ---- A17: strip invented source URLs --------------------------------------
def test_strip_invented_url_on_facilities():
    from core import pipeline
    from shared.contracts import ToolResult, Facility
    res = ToolResult(tool="directory", facilities=[Facility(id="1", name="X Pharmacy", type="pharmacy")])
    out = pipeline._strip_unsourced_urls("Nearest is X Pharmacy. Source: https://fake-pharmacy.com", res)
    assert "http" not in out            # facilities have no source -> link dropped


def test_keep_real_procedure_source_url():
    from core import pipeline
    from shared.contracts import ToolResult, Doc, Source
    real = "https://moph.gov.lb/real-page"
    res = ToolResult(tool="procedure",
                     docs=[Doc(id="1", title="T", content="c", source=Source(title="T", url=real))])
    kept = pipeline._strip_unsourced_urls(f"Steps... source: {real}", res)
    fake = pipeline._strip_unsourced_urls("Steps... source: https://made-up.example", res)
    assert real in kept                 # the genuine source survives
    assert "made-up" not in fake        # an invented one is removed


# ---- 0.3: follow-up town memory -------------------------------------------
def test_pending_town_followup_stitches_question(monkeypatch):
    from core import memory, pipeline
    # pretend "beirut" resolves to a caza; nothing else does
    monkeypatch.setattr(pipeline.router, "_resolve_caza",
                        lambda t: "Beirut" if "beirut" in t.lower() else None)
    # a user we never asked -> no stitch (nothing pending)
    assert pipeline._apply_pending_town(_inq("Beirut")).text == "Beirut"
    # a user we DID ask for a town -> their place answer is stitched on
    memory.remember_pending_town("u1", "nearest pharmacy")
    inq = _inq("Beirut").model_copy(update={"user_ref": "u1"})
    assert pipeline._apply_pending_town(inq).text == "nearest pharmacy Beirut"


def test_pending_town_ignored_for_new_question(monkeypatch):
    from core import memory, pipeline
    monkeypatch.setattr(pipeline.router, "_resolve_caza", lambda t: None)
    memory.remember_pending_town("u2", "nearest pharmacy")
    inq = _inq("how much is panadol").model_copy(update={"user_ref": "u2"})
    out = pipeline._apply_pending_town(inq)
    assert out.text == "how much is panadol"   # not stitched


# ---- A5: safety, multilingual ---------------------------------------------
@pytest.mark.parametrize("text", [
    "my father is not breathing",
    "بدي موت",
    "crise cardiaque",
])
def test_emergency(text):
    a = pipeline.handle(_inq(text))
    assert a.outcome == "emergency" and "140" in a.text


@pytest.mark.parametrize("text", [
    "what dose of panadol for my baby?",
    "كم حبة لازم آخذ",
    "quelle posologie",
])
def test_advice_refused(text):
    assert pipeline.handle(_inq(text)).outcome == "refused"


# ---- A3: grounding gate falls back when no tool result --------------------
def test_grounding_fallback(monkeypatch):
    monkeypatch.setattr(router, "route", lambda inq: ToolResult(tool="procedure"))
    a = pipeline.handle(_inq("something with no source"))
    assert a.grounded is False and a.outcome == "unanswered" and "1787" in a.text


# ---- A6: voice note is transcribed before routing -------------------------
def test_voice_note_transcribed(monkeypatch):
    monkeypatch.setattr(pipeline, "_fetch_audio", lambda url: b"fake-audio")
    a = pipeline.handle(_inq(text="", audio_url="https://example.com/vn.ogg"))
    # stub transcriber yields placeholder text -> pipeline still produces an answer
    assert a.text and a.outcome in {"answered", "unanswered"}


def test_unreadable_voice_note(monkeypatch):
    def boom(url):
        raise RuntimeError("fetch failed")
    monkeypatch.setattr(pipeline, "_fetch_audio", boom)
    a = pipeline.handle(_inq(text="", audio_url="https://example.com/vn.ogg"))
    assert a.outcome == "unanswered" and "couldn't read" in a.text

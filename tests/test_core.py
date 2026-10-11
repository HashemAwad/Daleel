"""Dev A core tests: routing, safety (multilingual), grounding gate, voice path."""
import pytest
from shared.contracts import Inquiry, ToolResult
from core import pipeline, router


def _inq(text="", audio_url=None, lang=None):
    return Inquiry(id="t", channel="web", text=text, user_ref="t", audio_url=audio_url, lang=lang)


def _semantic_plan(tool: str, query: str) -> dict:
    return {"intent": "health_question", "relation": "new", "safety": "none",
            "tool": tool, "facility_type": None, "location": None, "drug": None,
            "result_limit": 3, "ownership_filter": None, "reply_language": "en",
            "needs_clarification": False, "clarification_kind": "none",
            "clarification_question": "", "resolved_query": query, "reply": "",
            "confidence": 0.95, "model": "api:test"}


# ---- A4: routing picks the right tool -------------------------------------
@pytest.mark.parametrize("text,expected", [
    ("how do I get my cancer medicine from the ministry?", "procedure"),
    ("nearest pharmacy in Aley", "directory"),
    ("أقرب مستشفى", "directory"),
    ("combien coûte le Concor 5?", "medicine"),
    ("سعر الدوا", "medicine"),
    ("adde se3er el Concor 5?", "medicine"),
    ("pharmacie la plus proche", "directory"),
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
    monkeypatch.setattr(router.providers, "llm", FakeLLM())
    # text has no directory keywords, but the model says "directory"
    assert router.choose_tool(_inq("I want to find a place")) == "directory"


def test_semantic_router_understands_unlisted_arabizi_spelling(monkeypatch):
    class SemanticLLM:
        def classify(self, text, labels):
            return "directory"
    monkeypatch.setattr(router.providers, "llm", SemanticLLM())
    assert router.choose_tool(_inq("wena a2rab mestashfa?")) == "directory"


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


def test_llm_failover_uses_hosted_when_local_fails():
    from core.llm_failover import FailoverLLM

    class Broken:
        def generate(self, *args):
            raise RuntimeError("local model stopped")

    class Working:
        def generate(self, system, prompt, context=""):
            return "hosted answer"

    llm = FailoverLLM(Broken(), Working())
    assert llm.generate("system", "question", "facts") == "hosted answer"


def test_local_and_hosted_backends_keep_separate_model_names(monkeypatch):
    from core.llm_ollama import OllamaLLM
    from core.llm_hosted import HostedLLM
    import core.llm_ollama as ollama_module
    import core.llm_hosted as hosted_module

    monkeypatch.setattr(ollama_module.settings, "local_model", "qwen2.5:7b")
    monkeypatch.setattr(hosted_module.settings, "hosted_model", "gemini-3.6-flash")
    assert OllamaLLM().model == "qwen2.5:7b"
    assert HostedLLM(base_url="https://example.com", api_key="key").model == "gemini-3.6-flash"


def test_native_gemini_response_is_parsed(monkeypatch):
    from core.llm_hosted import HostedLLM
    import core.llm_hosted as hosted_module

    class Response:
        status_code = 200
        def raise_for_status(self):
            return None
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "grounded answer"}]}}]}

    seen = {}
    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs["headers"]
        return Response()

    monkeypatch.setattr(hosted_module.httpx, "post", fake_post)
    llm = HostedLLM(base_url="https://generativelanguage.googleapis.com/v1beta",
                    api_key="secret", model="gemini-3.6-flash")
    assert llm.generate("system", "question", "facts") == "grounded answer"
    assert seen["url"].endswith("/models/gemini-3.6-flash:generateContent")
    assert seen["headers"] == {"x-goog-api-key": "secret"}


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
    assert real not in kept             # channel renders the genuine source once
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


def test_directory_followup_keeps_hospital_and_requests_one(monkeypatch):
    from core import memory
    memory.remember_directory_kind("u3", "hospital")
    inq = _inq("I want the closest one").model_copy(update={"user_ref": "u3"})
    out = pipeline._apply_directory_followup(inq)
    assert isinstance(out, Inquiry)
    assert out.text == "closest hospital only one"


@pytest.mark.parametrize("text", ["a2rab wa7de pls", "a2rab wa7dE!!", "2a2rab we7de"])
def test_arabizi_closest_followup_requests_one(text, monkeypatch):
    from core import memory
    class SemanticLLM:
        def classify(self, text, labels):
            return "closest_one"
    monkeypatch.setattr(router.providers, "llm", SemanticLLM())
    memory.remember_directory_kind("u3-arabizi", "pharmacy")
    inq = _inq(text).model_copy(update={"user_ref": "u3-arabizi", "lang": "arabizi"})
    out = pipeline._apply_directory_followup(inq)
    assert isinstance(out, Inquiry)
    assert out.text == "closest pharmacy only one"


def test_arabizi_hospital_spelling_keeps_hospital_kind(monkeypatch):
    class SemanticLLM:
        def classify(self, text, labels):
            return "hospital"
    monkeypatch.setattr(router.providers, "llm", SemanticLLM())
    assert router._directory_kind("wena a2rab mestashfa?") == "hospital"


def test_unknown_facility_type_is_not_assumed_to_be_pharmacy(monkeypatch):
    class SemanticLLM:
        def classify(self, text, labels):
            return "unknown"
    monkeypatch.setattr(router.providers, "llm", SemanticLLM())
    result = router.run_tool("directory", _inq("what is closest to me?"))
    assert result.is_empty() and result.clarification == "facility_type"


def test_private_followup_explains_missing_ownership_data():
    from core import memory
    memory.remember_directory_kind("u4", "hospital")
    inq = _inq("I want the private ones").model_copy(update={"user_ref": "u4"})
    out = pipeline._apply_directory_followup(inq)
    assert out.tool == "directory"
    assert "private or public" in out.text
    assert "MediTrack" not in out.text
    assert out.outcome == "answered"


# ---- A5: safety, multilingual ---------------------------------------------
@pytest.mark.parametrize("text", [
    "my father is not breathing",
    "بدي موت",
    "crise cardiaque",
])
def test_emergency(text):
    a = pipeline.handle(_inq(text))
    assert a.outcome == "emergency" and "140" in a.text


def test_severe_chest_pain_is_emergency():
    a = pipeline.handle(_inq("I have severe chest pain"))
    assert a.outcome == "emergency" and "140" in a.text


@pytest.mark.parametrize("text", [
    "what dose of panadol for my baby?",
    "كم حبة لازم آخذ",
    "quelle posologie",
])
def test_advice_refused(text):
    assert pipeline.handle(_inq(text)).outcome == "refused"


def test_strength_in_price_question_is_not_mistaken_for_dosing():
    assert pipeline.safety.check(_inq("price of Concor 5 mg")) is None


# ---- A3: grounding gate falls back when no tool result --------------------
def test_grounding_fallback(monkeypatch):
    monkeypatch.setattr(pipeline.understanding, "interpret",
                        lambda *args: _semantic_plan("procedure", "missing procedure"))
    monkeypatch.setattr(router, "run_tool", lambda tool, inq, **hints: ToolResult(tool="procedure"))
    a = pipeline.handle(_inq("something with no source"))
    assert a.grounded is False and a.outcome == "unanswered" and "1787" in a.text


def test_unanswered_result_preserves_original_tool(monkeypatch):
    monkeypatch.setattr(pipeline.understanding, "interpret",
                        lambda *args: _semantic_plan("medicine", "unavailable medicine price"))
    monkeypatch.setattr(router, "run_tool", lambda tool, inq, **hints: ToolResult(tool="medicine"))
    a = pipeline.handle(_inq("price of unavailable medicine"))
    assert a.outcome == "unanswered" and a.tool == "medicine"


def test_missing_api_does_not_guess_with_legacy_router(monkeypatch):
    from core import providers, stubs
    monkeypatch.setattr(providers, "llm", stubs.StubLLM())
    a = pipeline._handle(_inq("nearest pharmacy"))
    assert a.outcome == "unanswered"
    assert "temporarily unavailable" in a.text


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

"""Tests for the schema-driven understanding contract and conversation state."""
import json

from shared.contracts import Facility, Inquiry, ToolResult
from core import memory, pipeline, providers, router, understanding


def _inq(text: str, user: str = "understanding-test") -> Inquiry:
    return Inquiry(id="u", channel="web", text=text, user_ref=user,
                   lat=33.8938, lon=35.5018)


class StructuredLLM:
    name = "hosted:test"

    def __init__(self, result: dict):
        self.result = result

    def generate_structured(self, system, prompt, schema):
        return self.result


def plan(**changes):
    value = {
        "intent": "health_question", "relation": "new", "tool": "directory",
        "facility_type": "hospital", "location": None, "drug": None,
        "result_limit": 3, "ownership_filter": None, "reply_language": "en",
        "needs_clarification": False, "clarification_kind": "none",
        "clarification_question": "", "resolved_query": "nearest hospital",
        "reply": "",
        "confidence": 0.95,
    }
    value.update(changes)
    return value


def test_structured_plan_is_validated(monkeypatch):
    monkeypatch.setattr(providers, "llm", StructuredLLM(plan(location="Beirut")))
    result = understanding.interpret("anything", ["Aley", "Beirut"], {})
    assert result["tool"] == "directory"
    assert result["facility_type"] == "hospital"
    assert result["location"] == "Beirut"


def test_invalid_structured_plan_is_rejected(monkeypatch):
    monkeypatch.setattr(providers, "llm", StructuredLLM(plan(tool="invented_tool")))
    assert understanding.interpret("anything", ["Beirut"], {}) is None


def test_middle_result_limit_is_normalized_not_discarded(monkeypatch):
    monkeypatch.setattr(providers, "llm", StructuredLLM(plan(result_limit=2)))
    result = understanding.interpret("anything", ["Beirut"], {})
    assert result is not None and result["result_limit"] == 3


def test_followup_inherits_only_structured_previous_entities():
    interp = plan(relation="follow_up", facility_type=None, location=None,
                  result_limit=1)
    hints = understanding.resolved_hints(
        interp, {"tool": "directory", "facility_type": "pharmacy", "caza": "Aley"})
    assert hints == {"facility_type": "pharmacy", "caza": "Aley", "limit": 1}


def test_new_request_never_inherits_old_facility():
    hints = understanding.resolved_hints(
        plan(relation="new", facility_type="hospital"),
        {"tool": "directory", "facility_type": "pharmacy", "caza": "Aley"})
    assert hints["facility_type"] == "hospital"
    assert "caza" not in hints


def test_pipeline_uses_single_plan_instead_of_old_directory_guess(monkeypatch):
    user = "new-overrides-old"
    memory.remember_context(user, {"tool": "directory", "facility_type": "pharmacy"})
    monkeypatch.setattr(understanding, "interpret", lambda text, cazas, context: plan())
    seen = {}

    def run(tool, inq, **hints):
        seen.update(hints)
        return ToolResult(tool="directory", facilities=[
            Facility(id="h", name="Hospital", type="hospital", distance_km=0.8)
        ])

    monkeypatch.setattr(router, "run_tool", run)
    answer = pipeline._handle(_inq("a new request", user))
    assert seen["facility_type"] == "hospital"
    assert "Hospital" in answer.text


def test_ambiguous_plan_asks_clarification_without_querying_tool(monkeypatch):
    monkeypatch.setattr(understanding, "interpret", lambda text, cazas, context: plan(
        tool="procedure", facility_type=None, needs_clarification=True,
        clarification_kind="meaning",
        clarification_question="Which Ministry service do you mean?"))
    monkeypatch.setattr(router, "run_tool", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("tool must not run before clarification")))
    answer = pipeline._handle(_inq("help with my application"))
    assert answer.outcome == "unanswered"
    assert "which" in answer.text.lower()


def test_full_conversation_is_given_to_next_interpretation(monkeypatch):
    user = "conversation-history"
    calls = []

    def interpret(text, cazas, context):
        calls.append((text, context))
        if len(calls) == 1:
            return plan(tool="procedure", facility_type=None,
                        needs_clarification=True, clarification_kind="meaning",
                        clarification_question=(
                            "Which Ministry application do you mean?"))
        return plan(tool="procedure", facility_type=None,
                    needs_clarification=True, clarification_kind="meaning",
                    clarification_question="Please choose 1 or 2.")

    monkeypatch.setattr(understanding, "interpret", interpret)
    first = pipeline.handle(_inq("help with my application", user))
    second = pipeline.handle(_inq("the hospital application", user))

    assert first.outcome == "unanswered"
    assert second.text == "Please choose 1 or 2."
    history = calls[1][1]["conversation"]
    assert history[0] == {"role": "user", "content": "help with my application"}
    assert "Ministry application" in history[1]["content"]


def test_followup_uses_standalone_query_for_retrieval(monkeypatch):
    user = "followup-query"
    memory.remember_turn(user, "show me hospitals in Beirut",
                         "Here are the nearest hospitals in Beirut.")
    monkeypatch.setattr(understanding, "interpret", lambda *args: plan(
        tool="procedure", facility_type=None, relation="follow_up",
        resolved_query="hospital admission procedure at Ministry expense"))
    seen = {}

    def run_tool(tool, inq, **hints):
        seen["text"] = inq.text
        return ToolResult(tool="procedure", docs=[])

    monkeypatch.setattr(router, "run_tool", run_tool)
    pipeline.handle(_inq("how do I get admitted through the Ministry?", user))

    assert seen["text"] == "hospital admission procedure at Ministry expense"


def test_location_clarification_is_ignored_when_channel_has_coordinates(monkeypatch):
    monkeypatch.setattr(understanding, "interpret", lambda text, cazas, context: plan(
        needs_clarification=True, clarification_kind="location",
        clarification_question="Which town?"))
    monkeypatch.setattr(router, "run_tool", lambda tool, inq, **hints: ToolResult(
        tool="directory", facilities=[Facility(
            id="h", name="Nearby Hospital", type="hospital", distance_km=0.4)]))
    answer = pipeline._handle(_inq("nearest hospital"))
    assert answer.outcome == "answered"
    assert "Nearby Hospital" in answer.text


def test_directory_answer_is_phrased_by_api_not_normal_renderer(monkeypatch):
    class AnsweringLLM(StructuredLLM):
        def generate(self, system, prompt, context=""):
            assert prompt == "pharmacies in Jbeil"
            assert "[facility] Jbeil Pharmacy" in context
            return "Here are pharmacies in Jbeil."

    monkeypatch.setattr(providers, "llm", AnsweringLLM(plan(
        tool="directory", facility_type="pharmacy", location="Jbeil",
        resolved_query="pharmacies in Jbeil")))
    monkeypatch.setattr(router, "run_tool", lambda *args, **kwargs: ToolResult(
        tool="directory", facilities=[Facility(
            id="p", name="Jbeil Pharmacy", type="pharmacy", caza="Jbeil")]))

    answer = pipeline._handle(_inq("what are pharmacies in Jbeil"))
    assert answer.text.startswith("Here are pharmacies in Jbeil.")
    assert answer.model == "hosted:test"


def test_gemini_structured_request_sends_schema(monkeypatch):
    from core.llm_hosted import HostedLLM
    import core.llm_hosted as hosted

    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": json.dumps({"ok": True})}]}}]}

    seen = {}
    def post(url, **kwargs):
        seen.update(kwargs["json"]["generationConfig"])
        return Response()

    monkeypatch.setattr(hosted.httpx, "post", post)
    result = HostedLLM("https://generativelanguage.googleapis.com/v1beta", "key", "model").generate_structured(
        "system", "prompt", {"type": "object", "properties": {"ok": {"type": "boolean"}}})
    assert result == {"ok": True}
    assert seen["responseMimeType"] == "application/json"
    assert "responseSchema" in seen


def test_hosted_failover_covers_structured_understanding():
    from core.llm_failover import FailoverLLM

    class Broken:
        name = "gemini:primary"
        def generate_structured(self, *args):
            raise RuntimeError("quota")

    class Working:
        name = "groq:backup"
        def generate_structured(self, *args):
            return {"ok": True}

    llm = FailoverLLM(Broken(), Working())
    assert llm.generate_structured("s", "p", {}) == {"ok": True}
    assert llm.name == "failover->groq:backup"

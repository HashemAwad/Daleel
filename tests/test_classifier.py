"""B5: classify() returns valid closed-vocabulary Metadata and never leaks raw text."""
import re
import pytest
from ai import classifier
from ai.classifier import classify, TOPICS


@pytest.fixture(autouse=True)
def _no_db(monkeypatch):
    monkeypatch.setattr(classifier, "_caza",
                        lambda text: "Aley" if ("عاليه" in text or "Aley" in text) else None)


@pytest.mark.parametrize("text,topic", [
    ("كيف آخذ دوا السرطان", "chronic_med"),
    ("how do I get insulin for diabetes", "chronic_med"),
    ("sokkari dawa", "chronic_med"),
    ("what is the price of Panadol", "acute_med"),
    ("quel est le prix de ce médicament", "acute_med"),
    ("بدي صيدلية قريبة", "directory"),
    ("nearest pharmacy to me", "directory"),
    ("pharmacie la plus proche", "directory"),
    ("كيف أحصل على بطاقة الضمان", "coverage"),
    ("is this covered by NSSF insurance", "coverage"),
    ("hospital admission referral letter", "referral_admission"),
    ("أحتاج تحويلة للمستشفى", "referral_admission"),
    ("كيف أحصل على شهادة ورقة معاملة", "procedures"),
    ("comment obtenir un certificat", "procedures"),
    ("أعاني من اكتئاب", "mental_health"),
    ("I need an ambulance, heart attack", "emergency"),
    ("hello", "other"),
    ("", "other"),
])
def test_topics(text, topic):
    assert classify(text).topic == topic


def test_topics_are_in_closed_list():
    for t in ["x", "اسعاف", "dawa", "free text 12345"]:
        assert classify(t).topic in TOPICS


def test_emergency_sets_outcome():
    assert classify("طوارئ نزيف").outcome == "emergency"
    assert classify("price of Panadol").outcome == "answered"


@pytest.mark.parametrize("text,lang", [
    ("كيف آخذ دوا السرطان", "ar"),
    ("bade dawa la sokkari ktir", "arabizi"),
    ("je voudrais la liste des médicaments", "fr"),
    ("j’ai une crise cardiaque", "fr"),
    ("how do I get the card", "en"),
])
def test_lang(text, lang):
    assert classify(text).lang == lang


def test_subtopic_and_caza():
    m = classify("دوا السرطان في عاليه")
    assert (m.subtopic, m.caza) == ("cancer", "Aley")
    assert classify("price of Panadol").subtopic is None


def test_no_pii_leaks_into_fields():
    """Even if redaction were skipped, no name/number/free text may reach the output."""
    raw = "اسمي محمد علي رقمي 70123456 هوية 123456789012 mail a@b.com بدي دوا السرطان"
    m = classify(raw)
    blob = " ".join(str(v) for v in m.model_dump().values() if v is not None)
    for leak in ("محمد", "70123456", "123456789012", "a@b.com"):
        assert leak not in blob
    assert re.fullmatch(r"[a-z_]{1,40}", m.topic)
    assert m.subtopic is None or re.fullmatch(r"[a-z_]{1,40}", m.subtopic)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", m.day)       # day only, no time


# ---- dashboard "kinds" (metadata.subtopic) ---------------------------------
@pytest.mark.parametrize("text,topic,kind", [
    ("كيف آخذ دوا السرطان", "procedures", "chronic_medication_approval"),
    ("how do I get the health coverage card", "procedures", "health_coverage_card"),
    ("hospital admission papers", "procedures", "hospital_admission"),
    ("medical certificate for school", "procedures", "medical_certificate"),
    ("what do I need for the stamp", "procedures", "other_paper"),
    ("price of insulin", "drug_price", "diabetes"),
    ("سعر بنادول", "drug_price", "pain_fever"),
    ("price of Concor 5", "drug_price", "heart_blood_pressure"),
    ("price of Lipitor", "drug_price", "other_medicine"),
    ("nearest pharmacy", "directory", "pharmacy"),
    ("مستشفى قريب", "directory", "hospital"),
])
def test_detail_kinds(text, topic, kind):
    assert classifier.detail(text, topic) == kind


def test_detail_is_none_for_topics_without_kinds_and_stays_in_the_closed_vocabulary():
    assert classifier.detail("anything", "other") is None
    assert classifier.detail("chest pain", "emergency") is None
    kinds = {k for table in classifier.DETAIL.values() for k, _ in table} | set(classifier._DETAIL_OTHER.values())
    assert all(re.fullmatch(r"[a-z_]{1,40}", k) for k in kinds)        # metadata.subtopic CHECK


def test_detail_never_returns_any_of_the_question_text():
    out = classifier.detail("اسمي محمد 70123456 دوا السكري", "drug_price")
    assert out == "diabetes" and "محمد" not in out and "70123456" not in out


def test_transcripts_kind_skips_refused_and_emergency_turns():
    from data import transcripts
    from shared.contracts import Answer
    ok = Answer(text="t", tool="procedure", outcome="answered")
    assert transcripts.kind("hospital admission", ok) == "hospital_admission"
    assert transcripts.kind("how much insulin", Answer(text="t", tool="none", outcome="refused")) is None
    assert transcripts.kind("heart attack", Answer(text="t", tool="hotline", outcome="emergency")) is None
    assert transcripts.kind("hello", Answer(text="t", tool="none", outcome="unanswered")) is None   # topic "other"

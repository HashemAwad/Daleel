"""Medicine lookup (D3). The matching is tested as a pure function; DB tests skip without Postgres."""
import pytest
from data import medicine
from data.medicine import MedicineLookupImpl, match, name_words, numbers

ROWS = [
    {"name": "CONCOR", "strength": "5mg", "form": "Tablet", "price": 870164},
    {"name": "CONCOR", "strength": "10mg", "form": "Tablet", "price": 1176665},
    {"name": "CONCOR COR", "strength": "2.5mg", "form": "Tablet", "price": 488906},
    {"name": "CONCOR AM 5", "strength": None, "form": "Tablet", "price": 1377012},
    {"name": "CONCOR T 5", "strength": None, "form": "Tablet", "price": 1457748},
    {"name": "CONCOR PLUS", "strength": None, "form": "Tablet", "price": None},
    {"name": "PANADOL NIGHT", "strength": None, "form": "Tablet", "price": 200000},
    {"name": "PANADOL JOINT", "strength": "665mg", "form": "Tablet", "price": 300000},
    {"name": "PROGRAF 0.5 MG", "strength": "0.5mg", "form": "Capsule", "price": 900000},
    {"name": "PROGRAF 5MG", "strength": "5mg", "form": "Capsule", "price": 950000},
    {"name": "GLUCOPHAGE", "strength": "1,000mg", "form": "Tablet", "price": 400000},
    {"name": "GLUCOPHAGE", "strength": "850mg", "form": "Tablet", "price": 350000},
    {"name": "Abremia 250 mg PO", "strength": "250 mg", "form": None, "price": None},
    {"name": "CHILDREN PANADOL", "strength": "120mg/5ml", "form": "Syrup", "price": 150000},
]


def _names(sentence):
    return [(r["name"], r["strength"], r["price"]) for r in match(sentence, ROWS)]


def test_name_words_and_numbers():
    assert name_words("CONCOR AM 5") == ["concor", "am"]
    assert name_words("Abremia 250 mg PO") == ["abremia"]
    assert name_words("PROGRAF 0.5 MG") == ["prograf"]
    assert numbers("Concor 5") == {5.0} and numbers("concor 2,5") == {2.5} == numbers("concor 2.5mg")
    assert numbers("glucophage 1,000") == {1000.0} and numbers("٥ mg") == {5.0}
    assert numbers("kam se3r el 7abbet 2arib") == set()          # Arabizi letters are not strengths


def test_exact_strength_keeps_its_price():
    assert _names("Combien coûte le Concor 5?") == [("CONCOR", "5mg", 870164)]
    assert _names("concor 10 price") == [("CONCOR", "10mg", 1176665)]
    assert _names("prix du glucophage 850") == [("GLUCOPHAGE", "850mg", 350000)]
    assert _names("glucophage 1,000 mg") == [("GLUCOPHAGE", "1,000mg", 400000)]


def test_decimal_never_matches_whole_number():
    assert _names("prograf 5") == [("PROGRAF 5MG", "5mg", 950000)]
    assert _names("prograf 0.5") == [("PROGRAF 0.5 MG", "0.5mg", 900000)]


def test_unknown_strength_or_drug_returns_nothing():
    assert _names("concor 20") == []
    assert _names("price of unicorn tears") == []
    assert _names("is lipitor free") == []
    assert _names("what is the cost of treatment in hospital") == []
    assert _names("concorr 5") == []                              # no typo tolerance, on purpose


def test_variant_needs_its_full_name():
    assert _names("concor plus") == [("CONCOR PLUS", None, None)]
    assert _names("concor am 5") == [("CONCOR AM 5", None, 1377012)]
    # "am" / "t" elsewhere in the sentence must not select the AM / T variants
    assert _names("i am asking the price of concor 5") == [("CONCOR", "5mg", 870164)]
    assert _names("t'as le prix du concor 5 ?") == [("CONCOR", "5mg", 870164)]


def test_several_products_come_back_without_prices():
    got = _names("how much is concor")                            # 5mg and 10mg
    assert [g[:2] for g in got] == [("CONCOR", "5mg"), ("CONCOR", "10mg")]
    assert all(price is None for *_, price in got)
    family = _names("how much is panadol")                        # no plain PANADOL row
    assert len(family) >= 2 and all(price is None for *_, price in family)


def test_single_family_match_never_carries_a_price():
    # "panadol" is not the product "PANADOL JOINT": even with one hit, no price may be quoted
    rows = [{"name": "ASPIRIN PROTECT", "strength": "100mg", "form": "Tablet", "price": 146479}]
    assert [(r["name"], r["price"]) for r in match("how much is aspirin", rows)] == [("ASPIRIN PROTECT", None)]
    assert [(r["name"], r["price"]) for r in match("aspirin protect price", rows)] == [("ASPIRIN PROTECT", 146479)]


def test_a_number_is_a_strength_only_with_a_unit_or_right_after_the_name():
    both = [("CONCOR", "5mg", None), ("CONCOR", "10mg", None)]
    assert _names("price of concor for 10 people") == both           # 10 is not a strength here
    assert _names("my mom takes 5 a day, concor price") == both
    assert _names("concor 5 for 10 days") == [("CONCOR", "5mg", 870164)]
    assert _names("2 boxes of concor 10") == [("CONCOR", "10mg", 1176665)]
    assert _names("10 mg concor") == [("CONCOR", "10mg", 1176665)]   # a unit counts anywhere
    assert _names("concor 20mg") == [] and _names("concor 2,5") == []


def test_ordinary_word_brand_is_not_a_family():
    assert _names("medicine for my children") == []


def test_alias_maps_arabic_spelling_to_brand(monkeypatch):
    monkeypatch.setitem(medicine.ALIASES, medicine.normalize("كونكور"), "concor")
    assert _names("سعر كونكور 5") == [("CONCOR", "5mg", 870164)]


def test_db_failure_returns_empty(monkeypatch):
    def boom():
        raise RuntimeError("secret row text")
    monkeypatch.setattr(medicine, "get_conn", boom)
    assert MedicineLookupImpl().find("concor 5") == []


# ---- against the real seed data -------------------------------------------------
@pytest.fixture(scope="module")
def lookup(db_ready):
    return MedicineLookupImpl()


def test_real_single_variant_brands_quote_no_price(lookup):
    for sentence in ["how much is aspirin", "diamicron price"]:
        got = lookup.find(sentence)
        assert got and all(d.price is None for d in got), sentence
    assert all(d.price is None for d in lookup.find("price of concor for 10 people"))


def test_real_concor_5(lookup):
    got = lookup.find("Combien coûte le Concor 5?")
    assert len(got) == 1
    assert got[0].name.startswith("CONCOR 5mg") and got[0].price > 0 and got[0].currency == "LBP"
    assert got[0].is_free is None


def test_real_misses_and_ambiguity(lookup):
    assert lookup.find("Concor 20") == []
    assert lookup.find("is lipitor free") == []
    assert lookup.find("price of unicorn tears") == []
    several = lookup.find("Concor")
    assert len(several) > 1 and all(d.price is None for d in several)


def test_chat_end_to_end(lookup, monkeypatch):
    from fastapi.testclient import TestClient
    from core.app import app
    from core import providers, stubs
    if not isinstance(providers.medicine, MedicineLookupImpl):
        pytest.skip("providers did not pick up the real lookup")
    monkeypatch.setattr(providers, "llm", stubs.StubLLM())      # don't depend on a model being installed
    body = TestClient(app).post("/chat", json={"channel": "web", "text": "Combien coûte le Concor 5?", "user_ref": "t"}).json()
    assert body["tool"] == "medicine" and body["grounded"] is True

"""Directory search + place resolution (D4). Pure tests need no DB; DB tests skip without Postgres."""
import pytest
from data import directory
from data.directory import DirectorySearchImpl, build_towns, order, resolve, resolve_caza
from data.normalize import place_key

ALIASES = {place_key(a): c for a, c in [
    ("Aley", "Aley"), ("aaley", "Aley"), ("3ale", "Aley"), ("عاليه", "Aley"),
    ("Chouf", "Chouf"), ("shouf", "Chouf"), ("الشوف", "Chouf"), ("شوف", "Chouf"),
    ("Sour", "Sour"), ("sur", "Sour"), ("tyre", "Sour"), ("صور", "Sour"),
    ("Jbeil", "Jbeil"), ("Bent Jbeil", "Bent Jbeil"), ("bint jbeil", "Bent Jbeil"),
    ("Beirut", "Beirut"), ("West Bekaa", "West Bekaa"),
]}
TOWNS = build_towns([
    {"address": "Choueifat El-Quoubbeh", "caza": "Aley"}, {"address": "Choueifat El-Oumara", "caza": "Aley"},
    {"address": "Jounie Ghadir", "caza": "Kesrwane"}, {"address": "Aaley", "caza": "Aley"},
    {"address": "Mazraa Yachouh", "caza": "El Meten"},                     # generic first word
    {"address": "Chiyah", "caza": "Baabda"}, {"address": "Chiyah", "caza": "Beirut"},   # two cazas
    {"address": "Toul", "caza": "El Nabatieh"},                            # too short
], ALIASES)


def _r(text):
    return resolve(text, ALIASES, TOWNS)


def test_build_towns_keeps_only_distinctive_single_caza_words():
    assert TOWNS == {"choueifat": "Aley", "jounie": "Kesrwane"}


@pytest.mark.parametrize("text", [
    "Aley", "3ale", "عاليه", "عالية", "bade saydaliyye 2arib mn Aley", "nearest pharmacy in Aley",
    "pharmacie à Aley svp", "صيدلية بعاليه", "saydaliyye b3aley",
])
def test_aley_in_every_spelling(text):
    assert _r(text) == ("Aley", None)


def test_town_resolves_to_its_caza_and_is_remembered():
    assert _r("pharmacy in Choueifat") == ("Aley", "choueifat")
    assert _r("bade saydaliyye b jounie") == ("Kesrwane", "jounie")
    assert _r("hospital near Jounieh") == ("Kesrwane", "jounie")
    assert _r("pharmacy in Mazraa") == (None, None)
    assert _r("pharmacy in Chiyah") == (None, None)


def test_ambiguous_words_need_a_location_word_inside_a_sentence():
    assert _r("pharmacie sur la route") == (None, None)          # "sur" = on
    assert _r("شوف وين في صيدلية") == (None, None)                # "شوف" = look
    assert _r("pharmacy in Sour") == ("Sour", None)
    assert _r("صيدلية بالشوف") == ("Chouf", None)
    assert _r("Sour") == ("Sour", None) and _r("شوف") == ("Chouf", None)   # a bare place name is taken at face value
    assert _r("bade shouf saydaliyye b Aley") == ("Aley", None)


def test_longest_phrase_and_first_mention_win():
    assert _r("hospital in Bint Jbeil") == ("Bent Jbeil", None)
    assert _r("hospital in Jbeil") == ("Jbeil", None)
    assert _r("pharmacy in west bekaa") == ("West Bekaa", None)
    assert _r("from Aley towards Beirut") == ("Aley", None)


def test_no_place():
    assert _r("") == _r(None) == _r("nearest pharmacy") == (None, None)


def test_order_puts_named_town_then_same_name_town_first():
    rows = [
        {"id": 1, "name": "Abou", "address": "Choueifat El-Quoubbeh"},
        {"id": 2, "name": "Zed", "address": "Aaley"},
        {"id": 3, "name": "Mid", "address": "Bchamoun"},
    ]
    assert [r["id"] for r in order(rows, "Aley", None, ALIASES)] == [2, 1, 3]
    assert [r["id"] for r in order(rows, "Aley", "choueifat", ALIASES)] == [1, 2, 3]


def test_db_failure_returns_empty(monkeypatch):
    def boom():
        raise RuntimeError("secret")
    monkeypatch.setattr(directory, "_tables", None)
    monkeypatch.setattr(directory, "get_conn", boom)
    assert DirectorySearchImpl().nearest("pharmacy", caza="Aley") == []
    assert resolve_caza("pharmacy in Aley") is None


# ---- against the real seed data -------------------------------------------------
@pytest.fixture(scope="module")
def search():
    from data.db import apply_schema
    from data.loaders import load
    try:
        apply_schema()
        load()
    except Exception:
        pytest.skip("Postgres not reachable")
    directory._tables = None
    return DirectorySearchImpl()


def test_d4_done_when(search):
    got = search.nearest("pharmacy", caza="Aley")
    assert len(got) == 3 and all(f.type == "pharmacy" and f.caza == "Aley" for f in got)
    assert all(place_key(f.address).startswith("aaley") for f in got)       # Aley town, not Choueifat
    assert all(f.distance_km is None for f in got)


def test_real_sentences(search):
    assert resolve_caza("bade saydaliyye 2arib mn Aley") == "Aley"
    demo = search.nearest("pharmacy", caza="bade saydaliyye 2arib mn Aley")
    assert len(demo) == 3 and demo[0].caza == "Aley"
    town = search.nearest("pharmacy", caza="pharmacy in Choueifat", k=5)
    assert len(town) == 5 and all(place_key(f.address).startswith("choueifat") for f in town)
    assert search.nearest("hospital", caza="مستشفى ببيروت")[0].caza == "Beirut"


def test_real_empty_cases(search):
    assert search.nearest("pharmacy") == []                       # no place
    assert search.nearest("pharmacy", caza="nearest pharmacy") == []
    assert search.nearest("pharmacy", caza="Atlantis") == []
    assert search.nearest("phc", caza="Aley") == []               # no PHCs loaded
    assert search.nearest("dentist", caza="Aley") == []

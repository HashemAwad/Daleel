"""Seed data + normaliser checks (D2). DB tests skip when Postgres isn't reachable."""
import pytest
from data.db import get_conn, apply_schema
from data.loaders import ingredient_key, load
from data.normalize import normalize, place_key


def test_normalize():
    assert normalize("Coûte  le CONCOR 5?") == "coute le concor 5"     # drug strength digit survives
    assert normalize("بَنادُول") == normalize("بنادول")
    assert normalize("أدوية") == "ادويه"
    assert normalize("٥ mg") == "5 mg"


def test_place_key_folds_arabizi_only_in_words():
    assert place_key("3ale") == place_key("Aale")
    assert place_key("عاليه") == place_key("عالية")
    assert place_key("2026") == "2026"


def test_ingredient_key():
    assert ingredient_key("Bisoprolol fumarate - 5mg, Amlodipine besylate - 5mg") == \
        "amlodipine besylate + bisoprolol fumarate"
    assert ingredient_key("Metformin HCl - 1,000mg") == "metformin hcl"
    assert ingredient_key("") is None


@pytest.fixture(scope="module")
def conn(db_ready):
    assert load() == load()              # idempotent
    c = get_conn()
    yield c
    c.close()


def test_missing_or_empty_seed_file_is_an_error_not_a_wipe(tmp_path, monkeypatch):
    from data import loaders
    monkeypatch.setattr(loaders, "SEEDS", tmp_path)
    with pytest.raises(FileNotFoundError):
        loaders.load()
    (tmp_path / "cazas.csv").write_text("name_en,name_ar,name_fr\n", encoding="utf-8")
    with pytest.raises(ValueError):
        loaders._rows("cazas.csv")
    assert loaders._rows("caza_aliases.csv", required=False) == []


def test_synthetic_flag_is_case_insensitive():
    from data.loaders import _true
    assert _true("true") and _true(" TRUE ") and _true("True") and not _true("false") and not _true("")


def _one(conn, sql, *params):
    return conn.execute(sql, params).fetchone()


def test_d2_done_when(conn):
    assert _one(conn, "SELECT count(*) AS n FROM hotlines")["n"] == 4
    assert _one(conn, "SELECT count(*) AS n FROM drugs")["n"] > 0


def test_no_zero_prices_and_every_row_has_a_source(conn):
    assert _one(conn, "SELECT count(*) AS n FROM drugs WHERE price <= 0 OR source IS NULL")["n"] == 0
    assert _one(conn, "SELECT count(*) AS n FROM facilities WHERE source IS NULL")["n"] == 0


def test_demo_rows_exist(conn):
    concor = _one(conn, "SELECT price, currency FROM drugs WHERE name_key = %s AND strength = '5mg'", normalize("Concor"))
    assert concor and concor["price"] > 0 and concor["currency"] == "LBP"
    assert _one(conn, "SELECT count(*) AS n FROM facilities WHERE type = 'pharmacy' AND caza = 'Aley'")["n"] > 0


@pytest.mark.parametrize("spelling", ["Aley", "3ale", "3aley", "عاليه", "عالية", "Aaley"])
def test_aley_spellings_resolve(conn, spelling):
    row = _one(conn, "SELECT caza FROM caza_aliases WHERE alias_key = %s", place_key(spelling))
    assert row and row["caza"] == "Aley"

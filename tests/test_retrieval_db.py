"""B0: retrieval.py can reach Postgres and SELECT from `procedures`.
Skipped when Postgres isn't reachable (same convention as test_data_schema.py)."""
import pytest
from ai import retrieval


@pytest.fixture(scope="module", autouse=True)
def _db_up():
    try:
        retrieval.ping()
    except Exception:
        pytest.skip("Postgres not reachable")


def test_ping():
    assert retrieval.ping() is True


def test_count_procedures_runs():
    assert retrieval.count_procedures() >= 0

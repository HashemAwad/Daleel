"""Shared test setup.

Turn recording is off for the whole suite, so tests that call pipeline.handle don't write
metadata rows into the dev database. The data tests switch it back on where they need it.

DB tests use the `db_ready` fixture. They RELOAD seed tables and DELETE idle transcripts, so:
  * they refuse to run when DALEEL_ENV=production (the demo server sets this) or the DB is not local
  * they skip only when Postgres is unreachable; a broken schema or loader fails loudly
  * REQUIRE_DB=1 turns that skip into a failure — use it for the pre-demo run
"""
import os
from urllib.parse import urlparse
import pytest

os.environ["RECORD_TURNS"] = "0"


@pytest.fixture(autouse=True)
def _hermetic_llm(monkeypatch):
    """Tests must never call a real LLM backend (no network, fast, deterministic).
    Pin the stub by default; tests that exercise a specific LLM monkeypatch
    providers.llm themselves and override this within their own scope."""
    from core import providers, stubs
    monkeypatch.setattr(providers, "llm", stubs.StubLLM(), raising=False)


class SilentTranscriber:
    """What every test gets unless it pins its own: hears nothing, loads nothing."""
    def transcribe(self, audio, mime=""):
        return "", None

    def ready(self):
        return True


@pytest.fixture(autouse=True)
def _hermetic_transcriber(monkeypatch):
    """Tests must never load or download a Whisper model through the app's wiring.
    Tests of ai.transcribe build their own TranscriberImpl with a fake model."""
    from core import providers
    real = providers.transcriber
    monkeypatch.setattr(providers, "transcriber", SilentTranscriber(), raising=False)
    return real                      # what the app is really wired to, for tests that ask


@pytest.fixture(scope="session")
def db_ready():
    import psycopg
    from shared.config import settings          # loads .env
    from data.db import apply_schema
    from data.loaders import load
    host = urlparse(settings.database_url).hostname
    if os.getenv("DALEEL_ENV") == "production" or host not in ("localhost", "127.0.0.1", "::1"):
        pytest.exit("refusing to run DB tests against a production or non-local database", returncode=2)
    try:
        apply_schema()
    except psycopg.OperationalError:
        if os.getenv("REQUIRE_DB") == "1":
            raise
        pytest.skip("Postgres not reachable (set REQUIRE_DB=1 to fail instead)")
    load()

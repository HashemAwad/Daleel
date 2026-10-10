"""Per-turn storage: one anonymous metadata row, plus the temporary transcript. Owner: D.

    transcripts.record(inq, answer)      # called once per turn from core.pipeline.handle; never raises

What is written, in two separate transactions (metadata first, so a transcript failure cannot lose it):
  metadata     One row per turn: topic / subtopic (kind) / caza / lang / outcome / day, derived from the route taken —
               no model call, no text, no session key. This is the only thing that is kept.
               Not written when RECORD_TURNS=0 or while backing off after a database outage.
  transcripts  ONLY for a trusted session ref and a non-default salt. Deleted by data.retention.
               Text is stored only when STORE_TRANSCRIPT_TEXT=1, after B's redactor + scrub();
               emergency and refusal turns never store text (that path skips redaction upstream).

Settings (env): RECORD_TURNS=0 switches this off entirely; STORE_TRANSCRIPT_TEXT=1 keeps scrubbed text.
Limits: B's redactor masks phones, IDs, emails and names introduced as "my name is ..."; scrub() is the
backstop for numbers and emails. A bare name, an address or a spelled-out number is NOT masked.
An operator with database access could still pair a metadata row with its transcript by insertion
order while the transcript exists; after retention deletes it, nothing links the two.
"""
from __future__ import annotations
import hashlib
import hmac
import logging
import os
import re
import time
import psycopg
from data.db import get_conn
from data.directory import resolve_caza
from shared.config import settings
from shared.contracts import Answer, Inquiry

log = logging.getLogger(__name__)
NO_TEXT = "[not stored]"
_WEAK_SALTS = {"", "change-me"}
_TRUSTED_REF = re.compile(r"(wa|web)_[0-9a-f]{32}")      # the format channels.identity mints
_LANGS = {"ar", "arabizi", "fr", "en"}
_NO_DETAIL = {"emergency", "refused"}                    # no text and no caza for these outcomes
_TOPIC_BY_TOOL = {"procedure": "procedures", "directory": "directory", "medicine": "drug_price"}

_ARABIC_DIGITS = {0x0660 + i: str(i) for i in range(10)} | {0x06F0 + i: str(i) for i in range(10)}
MAX_TEXT = 2000                                           # stored text is cut to this before any regex runs
# NUL (Postgres rejects it) and invisible direction / zero-width marks that hide inside Arabic numbers
_INVISIBLE = re.compile("[\x00\u200b-\u200f\u202a-\u202e\u2060\ufeff]")
_EMAIL = re.compile(r"[\w.+-]{1,64}@[\w-]{1,63}(?:\.[\w-]{1,63})+")     # bounded: no quadratic scan
# 6+ digits, allowing up to 3 separators between digits: 03/123456, 70 123 456, 03  123  456, 03_123_456
_NUMBER = re.compile(r"[+(]{0,2}\d(?:[\s\-./_()]{0,3}\d){5,}")
_DB_BACKOFF_SECONDS = 30
_down_until = 0.0                                          # after a DB failure, skip writes briefly


def scrub(text: str | None) -> str:
    t = _INVISIBLE.sub("", (text or "")[:MAX_TEXT]).translate(_ARABIC_DIGITS)
    return _NUMBER.sub("[number]", _EMAIL.sub("[email]", t))


def topic(answer: Answer) -> str:
    if answer.outcome == "emergency":
        return "emergency"
    if answer.outcome == "refused":
        return "dosing_request"
    return _TOPIC_BY_TOOL.get(answer.tool, "other")


def kind(text: str | None, answer: Answer) -> str | None:
    """Closed-vocabulary kind of paper / medicine / place (ai.classifier.detail), or None. No text is kept."""
    if answer.outcome in _NO_DETAIL:
        return None
    try:
        from ai.classifier import detail
        return detail(text or "", topic(answer))
    except Exception:
        return None


def session_key(user_ref: str | None) -> str | None:
    """Key for the transcripts table, or None when the turn must not be stored against a session:
    default salt (hashes of phone numbers would be guessable) or a ref we did not mint ("anon", client-made)."""
    salt = settings.session_hash_salt
    if salt in _WEAK_SALTS or not _TRUSTED_REF.fullmatch(user_ref or ""):
        return None
    return hmac.new(salt.encode(), b"transcript:" + user_ref.encode(), hashlib.sha256).hexdigest()


def _storable(text: str | None, answer: Answer) -> str:
    if os.getenv("STORE_TRANSCRIPT_TEXT") != "1" or answer.outcome in _NO_DETAIL or not (text or "").strip():
        return NO_TEXT
    try:
        from core import providers                         # late import: core imports this module
        return scrub(providers.redact(text[:MAX_TEXT]))
    except Exception:
        return NO_TEXT


_INSERT_TURN = (
    "INSERT INTO transcripts (session_hash, turn, role, text, outcome, tool, lang) "
    "SELECT %s, COALESCE(MAX(turn), 0) + 1, %s, %s, %s, %s, %s FROM transcripts WHERE session_hash = %s"
)


def record(inq: Inquiry, answer: Answer) -> bool:
    """Store one turn. Returns True if written. Never raises, never logs text."""
    global _down_until
    if os.getenv("RECORD_TURNS") == "0" or time.monotonic() < _down_until:
        return False
    try:
        detail = answer.outcome not in _NO_DETAIL
        lang = answer.lang or inq.lang
        lang = lang if lang in _LANGS else None
        caza = resolve_caza(inq.text) if detail else None
        subtopic = kind(inq.text, answer)
        with get_conn() as conn:                             # 1. the anonymous count, on its own
            conn.execute(
                "INSERT INTO metadata (topic, subtopic, caza, lang, outcome, day) "
                "VALUES (%s, %s, %s, %s, %s, (now() AT TIME ZONE 'Asia/Beirut')::date)",
                (topic(answer), subtopic, caza, lang, answer.outcome))
        key = session_key(inq.user_ref)
        if key:
            user_text, bot_text = _storable(inq.text, answer), _storable(answer.text, answer)
            with get_conn() as conn:                         # 2. the temporary transcript
                # one writer per session at a time, so two quick messages can't claim the same turn number
                conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
                conn.execute(_INSERT_TURN, (key, "user", user_text, None, None, lang, key))
                conn.execute(_INSERT_TURN, (key, "assistant", bot_text, answer.outcome, answer.tool, lang, key))
        return True
    except psycopg.OperationalError as e:                    # database unreachable: back off, so an
        _down_until = time.monotonic() + _DB_BACKOFF_SECONDS  # emergency reply never waits on a dead DB twice
        log.warning("turn not recorded, backing off %ds: %s", _DB_BACKOFF_SECONDS, type(e).__name__)
        return False
    except Exception as e:                                   # one bad turn must not silence the others
        log.warning("turn not recorded: %s", type(e).__name__)
        return False

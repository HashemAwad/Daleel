"""Phase-2 dashboard read API. Owner: C.

Reads ONLY the `metadata` table (topic, subtopic, caza, lang, outcome, day) —
the anonymised rows D's retention job writes after deleting transcripts. By
contract those columns hold no free text, numbers, or names, so everything here
is safe to put on a ministry screen.

Until the schema and the retention job land, the endpoint serves clearly
labelled mock rows (`"source": "mock"`) so the page is demo-able today.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from shared.config import settings

log = logging.getLogger("daleel.channels.metrics")

router = APIRouter(tags=["dashboard"])

ESCALATED_OUTCOMES = {"escalated", "emergency"}

# k-anonymity: never publish a breakdown cell representing fewer than this many
# conversations. topic + caza + day can single out one person in a small caza,
# and this endpoint feeds a screen a ministry would look at.
MIN_CELL = 5

# Shaped like real rows so the page layout is honest about what Phase 2 shows.
#
# Topics MUST be the vocabulary that actually reaches `metadata`. Exactly two
# writers exist and they agree on six values:
#   * real turns  — `data.transcripts.topic()`: the `_TOPIC_BY_TOOL` values
#                   (procedures / directory / drug_price) plus `emergency`
#                   (outcome emergency), `dosing_request` (outcome refused)
#                   and `other` (anything unrouted).
#   * rehearsals  — `data.demo._TOPICS`, seeded by `infra/reset_demo.sh`.
# `ai.classifier.TOPICS` is a THIRD, wider vocabulary (coverage, chronic_med,
# mental_health, ...) that nothing writes: the classifier is not called at
# runtime (open items B6 / H2). Mocking those names made the mock view a
# different page from the live one — `drug_price`, a quarter of every seeded
# rehearsal, was missing from it entirely.
#
# Kept as a literal rather than importing data: channels does not depend on
# another owner's module. tests/test_channels.py asserts the two agree.
MOCK_TOPICS = ("procedures", "directory", "drug_price",
               "dosing_request", "emergency", "other")

# Proportions and outcome rules follow `data.demo.sample_rows` so the mock and
# the rehearsal seed tell the same story: `other` is never answered, drug_price
# is answered ~60% of the time, and `emergency` / `dosing_request` carry no caza
# (the real writer drops it for those outcomes — `transcripts._NO_DETAIL`).
# Caza labels are canonical `cazas.name_en` values, which is what the column is
# a foreign key to — an alias like "Metn" or "Nabatieh" could never appear live.
# Bcharre is deliberately left under MIN_CELL so the page still demonstrates
# k-anonymity suppression on mock data.
MOCK_ROWS: list[dict[str, Any]] = [
    {"topic": "procedures", "caza": "Beirut", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 18},
    {"topic": "procedures", "caza": "Akkar", "lang": "ar", "outcome": "answered", "day": "2026-10-09", "n": 13},
    {"topic": "procedures", "caza": "Tripoli", "lang": "arabizi", "outcome": "answered", "day": "2026-10-10", "n": 11},
    {"topic": "procedures", "caza": "El Meten", "lang": "ar", "outcome": "unanswered", "day": "2026-10-10", "n": 11},
    {"topic": "procedures", "caza": "Kesrwane", "lang": "fr", "outcome": "unanswered", "day": "2026-10-09", "n": 7},
    {"topic": "directory", "caza": "Beirut", "lang": "arabizi", "outcome": "answered", "day": "2026-10-10", "n": 20},
    {"topic": "directory", "caza": "Baabda", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 14},
    {"topic": "directory", "caza": "Zahle", "lang": "en", "outcome": "answered", "day": "2026-10-09", "n": 8},
    {"topic": "directory", "caza": "Sour", "lang": "ar", "outcome": "unanswered", "day": "2026-10-09", "n": 8},
    {"topic": "drug_price", "caza": "Beirut", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 14},
    {"topic": "drug_price", "caza": "Aley", "lang": "arabizi", "outcome": "answered", "day": "2026-10-10", "n": 13},
    {"topic": "drug_price", "caza": "Bcharre", "lang": "ar", "outcome": "answered", "day": "2026-10-09", "n": 3},
    {"topic": "drug_price", "caza": "Saida", "lang": "ar", "outcome": "unanswered", "day": "2026-10-09", "n": 12},
    {"topic": "drug_price", "caza": "Baalbek", "lang": "en", "outcome": "unanswered", "day": "2026-10-10", "n": 8},
    {"topic": "other", "caza": "Beirut", "lang": "en", "outcome": "unanswered", "day": "2026-10-10", "n": 12},
    {"topic": "other", "caza": None, "lang": "fr", "outcome": "unanswered", "day": "2026-10-09", "n": 8},
    {"topic": "dosing_request", "caza": None, "lang": "ar", "outcome": "refused", "day": "2026-10-10", "n": 7},
    {"topic": "dosing_request", "caza": None, "lang": "arabizi", "outcome": "refused", "day": "2026-10-09", "n": 5},
    {"topic": "emergency", "caza": None, "lang": "ar", "outcome": "emergency", "day": "2026-10-10", "n": 5},
    {"topic": "emergency", "caza": None, "lang": "arabizi", "outcome": "emergency", "day": "2026-10-09", "n": 3},
]

_SQL = """
SELECT topic, caza, lang, outcome, day::text AS day, COUNT(*) AS n
FROM metadata
GROUP BY topic, caza, lang, outcome, day
"""


def _fetch_rows() -> list[dict[str, Any]]:
    """Grouped metadata rows. Raises if the DB or table isn't there yet."""
    try:
        from data.db import get_conn  # D's helper: dict rows + a sane timeout
    except Exception:
        import psycopg
        from psycopg.rows import dict_row

        def get_conn():  # type: ignore[misc]
            return psycopg.connect(
                settings.database_url, row_factory=dict_row, connect_timeout=2
            )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_SQL)
            return [dict(r) for r in cur.fetchall()]


def _tally(rows: list[dict[str, Any]], key: str,
           min_cell: int = MIN_CELL, top: int | None = None) -> list[dict[str, Any]]:
    """Counts per label, with small groups suppressed.

    Any label seen fewer than `min_cell` times is withheld and rolled into a
    single `withheld` entry. Publishing "drug_price · Bcharre · 1" on a
    ministry screen can identify the one person who asked; the rolled-up count
    keeps the totals honest without naming the group.

    `top` caps how many *published* labels come back. The `withheld` entry is
    never part of that cap: it sorts last by design, so a plain slice at the
    call site would drop the suppression notice exactly when there is enough
    data to need one — 26 cazas exist and a rehearsal seeds 12 labels, so the
    notice fell off the end of the list while suppression was still happening.
    """
    totals: dict[str, int] = {}
    for r in rows:
        label = r.get(key) or "unspecified"
        totals[str(label)] = totals.get(str(label), 0) + int(r.get("n", 1))

    published = {k: v for k, v in totals.items() if v >= min_cell}
    suppressed = {k: v for k, v in totals.items() if v < min_cell}

    ordered = sorted(published.items(), key=lambda kv: (-kv[1], kv[0]))
    if top is not None:
        ordered = ordered[:top]
    out = [{"label": k, "count": v} for k, v in ordered]
    if suppressed:
        out.append({
            "label": "withheld",
            "count": sum(suppressed.values()),
            "suppressed": True,
            "groups": len(suppressed),   # how many, never which
        })
    return out


def summarise(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    total = sum(int(r.get("n", 1)) for r in rows)

    # Headline figures come from the raw rows, not the suppressed tally: a
    # whole-service count identifies nobody, and silently dropping a small
    # outcome would under-report escalations — the opposite of useful.
    raw_outcomes: dict[str, int] = {}
    for r in rows:
        raw_outcomes[str(r.get("outcome") or "unspecified")] = (
            raw_outcomes.get(str(r.get("outcome") or "unspecified"), 0) + int(r.get("n", 1))
        )
    escalated = sum(v for k, v in raw_outcomes.items() if k in ESCALATED_OUTCOMES)
    unanswered = raw_outcomes.get("unanswered", 0)

    def pct(part: int) -> float:
        return round(100 * part / total, 1) if total else 0.0

    return {
        "source": source,            # "metadata" (real) or "mock"
        "total_turns": total,
        "unanswered": unanswered,
        "unanswered_rate": pct(unanswered),
        "escalations": escalated,
        "escalation_rate": pct(escalated),
        "refused": raw_outcomes.get("refused", 0),
        "answered": raw_outcomes.get("answered", 0),
        # stated on the page so a ministry reader knows why a row is missing
        "min_cell": MIN_CELL,
        # Real data starts at one row and grows. Below the threshold every
        # breakdown is withheld by design, which looks identical to a broken
        # page — so say which it is rather than letting the reader guess.
        "sparse": source != "mock" and total < MIN_CELL,
        "topics": _tally(rows, "topic", top=10),
        "languages": _tally(rows, "lang"),
        "cazas": _tally(rows, "caza", top=10),
        "outcomes": _tally(rows, "outcome"),
        "days": sorted(_tally(rows, "day"), key=lambda d: d["label"]),
        "unanswered_topics": _tally(
            [r for r in rows if r.get("outcome") == "unanswered"], "topic", top=5
        ),
    }


@router.get("/api/metrics")
def metrics() -> dict[str, Any]:
    """Anonymised aggregates for the Phase-2 dashboard."""
    try:
        rows = _fetch_rows()
        if rows:
            return summarise(rows, "metadata")
        log.info("metadata table reachable but empty — serving mock aggregates")
    except Exception as exc:
        log.info("metadata unavailable (%s) — serving mock aggregates", type(exc).__name__)
    return summarise(MOCK_ROWS, "mock")

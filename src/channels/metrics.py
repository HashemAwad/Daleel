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
# Topics are snake_case to match the schema's CHECK (topic ~ '^[a-z_]{1,40}$');
# the dashboard humanises them for display.
MOCK_ROWS: list[dict[str, Any]] = [
    {"topic": "chronic_medication_card", "caza": "Beirut", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 34},
    {"topic": "chronic_medication_card", "caza": "Aley", "lang": "arabizi", "outcome": "answered", "day": "2026-10-10", "n": 12},
    {"topic": "hospital_admission", "caza": "Tripoli", "lang": "ar", "outcome": "answered", "day": "2026-10-10", "n": 27},
    {"topic": "hospital_admission", "caza": "Saida", "lang": "ar", "outcome": "unanswered", "day": "2026-10-09", "n": 9},
    {"topic": "pharmacy_locator", "caza": "Beirut", "lang": "arabizi", "outcome": "answered", "day": "2026-10-10", "n": 22},
    {"topic": "pharmacy_locator", "caza": "Zahle", "lang": "en", "outcome": "answered", "day": "2026-10-09", "n": 8},
    {"topic": "drug_price", "caza": "Beirut", "lang": "fr", "outcome": "answered", "day": "2026-10-10", "n": 19},
    {"topic": "drug_price", "caza": "Baabda", "lang": "ar", "outcome": "unanswered", "day": "2026-10-10", "n": 7},
    {"topic": "vaccination", "caza": "Akkar", "lang": "ar", "outcome": "answered", "day": "2026-10-09", "n": 16},
    {"topic": "newborn_registration", "caza": "Keserwan", "lang": "fr", "outcome": "answered", "day": "2026-10-09", "n": 6},
    {"topic": "mental_health", "caza": "Beirut", "lang": "arabizi", "outcome": "escalated", "day": "2026-10-10", "n": 5},
    {"topic": "emergency", "caza": "Nabatieh", "lang": "ar", "outcome": "emergency", "day": "2026-10-10", "n": 4},
    {"topic": "dosing_request", "caza": "Beirut", "lang": "en", "outcome": "refused", "day": "2026-10-10", "n": 6},
    {"topic": "cancer_medicine", "caza": "Metn", "lang": "ar", "outcome": "answered", "day": "2026-10-09", "n": 11},
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
           min_cell: int = MIN_CELL) -> list[dict[str, Any]]:
    """Counts per label, with small groups suppressed.

    Any label seen fewer than `min_cell` times is withheld and rolled into a
    single `withheld` entry. Publishing "mental_health · Bcharre · 1" on a
    ministry screen can identify the one person who asked; the rolled-up count
    keeps the totals honest without naming the group.
    """
    totals: dict[str, int] = {}
    for r in rows:
        label = r.get(key) or "unspecified"
        totals[str(label)] = totals.get(str(label), 0) + int(r.get("n", 1))

    published = {k: v for k, v in totals.items() if v >= min_cell}
    suppressed = {k: v for k, v in totals.items() if v < min_cell}

    ordered = sorted(published.items(), key=lambda kv: (-kv[1], kv[0]))
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
        "topics": _tally(rows, "topic")[:10],
        "languages": _tally(rows, "lang"),
        "cazas": _tally(rows, "caza")[:10],
        "outcomes": _tally(rows, "outcome"),
        "days": sorted(_tally(rows, "day"), key=lambda d: d["label"]),
        "unanswered_topics": _tally(
            [r for r in rows if r.get("outcome") == "unanswered"], "topic"
        )[:5],
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

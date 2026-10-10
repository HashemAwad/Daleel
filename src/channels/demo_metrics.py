"""Synthetic metadata rows for the dashboard's DEMO mode. Owner: C.

    DASHBOARD_DEMO=1            serve these rows instead of the database (whole server)
    /api/metrics?demo=1         serve them for one request (the dashboard's "Show demo data" link)
    PYTHONPATH=src python -m channels.demo_metrics      # preview: row/day/topic counts, nothing written

These rows are generated in memory every time and are NEVER written to the database, so they cannot
be mixed with, or later mistaken for, real citizen questions. There is nothing to seed and nothing
to reset: switching the flag off returns the page to real data. Same closed vocabulary as the live
writer (`data.transcripts`), same suppression rule (5) as real data. Deterministic for a given day.
"""
from __future__ import annotations

import random
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

DAYS = 30
TURNS = 300
_BEIRUT = timezone(timedelta(hours=3))

_TOPICS = [("procedures", 30), ("directory", 25), ("drug_price", 25), ("other", 10),
           ("emergency", 4), ("dosing_request", 6)]
_CAZAS = [("Beirut", 22), ("Baabda", 14), ("El Meten", 12), ("Tripoli", 10), ("Aley", 8), ("Saida", 8),
          ("Zahle", 7), ("Kesrwane", 6), ("Sour", 5), ("Akkar", 4), ("Baalbek", 4), ("Bcharre", 1)]
_LANGS = [("ar", 45), ("arabizi", 25), ("en", 15), ("fr", 15)]
# kinds per topic (same closed vocabulary as ai.classifier.DETAIL), weighted
_KINDS = {
    "procedures": [("health_coverage_card", 30), ("chronic_medication_approval", 24), ("hospital_admission", 20),
                   ("medical_certificate", 12), ("disability_card", 6), ("vaccination", 4), ("other_paper", 4)],
    "drug_price": [("cancer", 22), ("diabetes", 20), ("heart_blood_pressure", 18), ("pain_fever", 14),
                   ("antibiotics", 10), ("asthma_allergy", 6), ("other_medicine", 10)],
    "directory": [("pharmacy", 55), ("hospital", 25), ("health_center", 20)],
}
_ANSWERED_SHARE = {"procedures": 0.7, "directory": 0.85, "drug_price": 0.6, "other": 0.0}
# a few "escalated" turns so every outcome appears; they carry no topic detail
_ESCALATED_SHARE = 0.02


def _pick(rng: random.Random, weighted: list[tuple]):
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


def today_beirut() -> date:
    return datetime.now(_BEIRUT).date()


def demo_rows(today: date | None = None, days: int = DAYS, turns: int = TURNS,
              seed: int = 11) -> list[dict[str, Any]]:
    """Aggregated rows shaped like the real query: {topic, caza, lang, outcome, day, n}."""
    today = today or today_beirut()
    rng = random.Random(seed)
    # busier on weekdays, gently rising over the month
    day_weights = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        day_weights.append((1.0 + 0.8 * i / days) * (0.6 if d.weekday() in (4, 5) else 1.0))
    counts: Counter = Counter()
    for _ in range(turns):
        offset = rng.choices(range(days), weights=day_weights)[0]
        day = (today - timedelta(days=days - 1 - offset)).isoformat()
        topic = _pick(rng, _TOPICS)
        if topic == "emergency":
            outcome, caza = "emergency", None
        elif topic == "dosing_request":
            outcome, caza = "refused", None
        elif topic != "other" and rng.random() < _ESCALATED_SHARE:
            outcome, caza = "escalated", _pick(rng, _CAZAS)
        else:
            outcome = "answered" if rng.random() < _ANSWERED_SHARE[topic] else "unanswered"
            caza = _pick(rng, _CAZAS)
        kind = _pick(rng, _KINDS[topic]) if topic in _KINDS else None
        counts[(topic, kind, caza, _pick(rng, _LANGS), outcome, day)] += 1
    return [{"topic": t, "subtopic": k, "caza": c, "lang": l, "outcome": o, "day": d, "n": n}
            for (t, k, c, l, o, d), n in sorted(counts.items(), key=lambda kv: (kv[0][5], str(kv[0])))]


if __name__ == "__main__":
    rows = demo_rows()
    print(f"{sum(r['n'] for r in rows)} synthetic turns in {len(rows)} aggregated rows (not stored anywhere)")
    for key in ("topic", "lang", "outcome", "caza"):
        c = Counter()
        for r in rows:
            c[r[key] or "unspecified"] += r["n"]
        print(f"  {key}: {dict(c.most_common())}")
    print(f"  days: {len({r['day'] for r in rows})}")

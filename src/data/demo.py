"""Demo reset: put the database back into a known state for a rehearsal. Owner: D.

    bash infra/reset_demo.sh                 # reload seeds, clear transcripts + metadata, add sample metadata
    bash infra/reset_demo.sh --no-sample     # same, but leave metadata empty

DESTRUCTIVE: deletes every row in `transcripts` and `metadata`. Refuses to run without --yes
(the shell wrapper passes it).

The sample metadata is MADE UP so the dashboard has something to show. Every sample row is
marked `subtopic = 'sample'`; rows written by real chats have no subtopic. Say so when presenting.
"""
from __future__ import annotations
import argparse
import random
import sys
from data.db import get_conn
from data.loaders import load

SAMPLE = "sample"
_TOPICS = [("procedures", 30), ("directory", 25), ("drug_price", 25), ("other", 10),
           ("emergency", 4), ("dosing_request", 6)]
_CAZAS = [("Beirut", 22), ("Baabda", 14), ("El Meten", 12), ("Tripoli", 10), ("Aley", 8), ("Saida", 8),
          ("Zahle", 7), ("Kesrwane", 6), ("Sour", 5), ("Akkar", 4), ("Baalbek", 4), (None, 20)]
_LANGS = [("ar", 45), ("arabizi", 25), ("en", 15), ("fr", 15)]
_ANSWERED_SHARE = {"procedures": 0.7, "directory": 0.85, "drug_price": 0.6, "other": 0.0}


def _pick(rng: random.Random, weighted: list[tuple]):
    return rng.choices([v for v, _ in weighted], weights=[w for _, w in weighted])[0]


def sample_rows(n: int = 320, days: int = 7, seed: int = 7) -> list[tuple]:
    """(topic, subtopic, caza, lang, outcome, days_ago) — deterministic, closed vocabulary only."""
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        topic = _pick(rng, _TOPICS)
        if topic == "emergency":
            outcome, caza = "emergency", None           # same rule as real turns: no caza for these
        elif topic == "dosing_request":
            outcome, caza = "refused", None
        else:
            outcome = "answered" if rng.random() < _ANSWERED_SHARE[topic] else "unanswered"
            caza = _pick(rng, _CAZAS)
        rows.append((topic, SAMPLE, caza, _pick(rng, _LANGS), outcome, rng.randrange(days)))
    return rows


def reset(with_sample: bool = True) -> dict:
    counts = load()
    with get_conn() as conn:
        counts["transcripts_deleted"] = conn.execute("DELETE FROM transcripts").rowcount
        counts["metadata_deleted"] = conn.execute("DELETE FROM metadata").rowcount
        rows = sample_rows() if with_sample else []
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO metadata (topic, subtopic, caza, lang, outcome, day) "
                "VALUES (%s, %s, %s, %s, %s, (now() AT TIME ZONE 'Asia/Beirut')::date - %s::int)", rows)
        counts["sample_metadata"] = len(rows)
    return counts


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Reset Daleel demo data (deletes transcripts and metadata)")
    ap.add_argument("--yes", action="store_true", help="confirm the deletion")
    ap.add_argument("--no-sample", action="store_true", help="leave metadata empty")
    args = ap.parse_args()
    if not args.yes:
        sys.exit("refusing: this deletes all transcripts and metadata. Re-run with --yes.")
    print(reset(with_sample=not args.no_sample))

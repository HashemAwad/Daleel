"""Demo sample rows (D7). Pure: reset() itself is destructive and is exercised by infra/reset_demo.sh."""
import os
import re
import subprocess
import sys
from data.demo import SAMPLE, sample_rows

OUTCOMES = {"answered", "unanswered", "escalated", "refused", "emergency"}


def test_sample_rows_are_deterministic_and_closed_vocabulary():
    rows = sample_rows()
    assert rows == sample_rows() and len(rows) == 320
    for topic, subtopic, caza, lang, outcome, days_ago in rows:
        assert re.fullmatch(r"[a-z_]{1,40}", topic) and subtopic == SAMPLE
        assert lang in {"ar", "arabizi", "fr", "en"} and outcome in OUTCOMES and 0 <= days_ago < 7
        if outcome in {"emergency", "refused"}:
            assert caza is None


def test_reset_refuses_without_yes():
    # a near-empty environment on purpose (no DATABASE_URL, nothing inherited), but on Windows Python
    # needs SYSTEMROOT to initialise sockets: without it importing psycopg fails before the check runs
    env = {"PYTHONPATH": "src", **{k: os.environ[k] for k in ("SYSTEMROOT",) if k in os.environ}}
    r = subprocess.run([sys.executable, "-m", "data.demo"], capture_output=True, text=True, env=env)
    assert r.returncode != 0 and "refusing" in r.stderr

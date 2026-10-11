"""Ingest small, manually verified official facts that live in repo seed JSON.

Use for official PDFs/tables whose structure the generic web extractor cannot
reliably preserve. Every record must retain its authoritative URL.
"""
from __future__ import annotations

import json
from pathlib import Path

from ai.ingest import ingest_text

SEED_FILE = Path(__file__).resolve().parents[1] / "data" / "seeds" / "verified_procedures.json"


def main() -> int:
    records = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    total = 0
    for record in records:
        count = ingest_text(record["url"], record["title"], record["content"], record["lang"])
        total += count
        print(f'{record["title"]}: {count} chunks')
    print(f"total chunks inserted: {total}")
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())

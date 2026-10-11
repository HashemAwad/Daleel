"""Load every verified URL in ``procedure_urls.txt`` into procedure retrieval.

The text file is a manifest, not runtime knowledge by itself. This command turns
its pages into searchable database chunks and reports every skipped or failed URL.

    PYTHONPATH=src python -m ai.ingest_manifest
    PYTHONPATH=src python -m ai.ingest_manifest --refresh

By default, URLs already represented in ``procedures`` are skipped. ``--refresh``
re-fetches them; each successful URL replaces only its own previous chunks.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ai.ingest import ingest_url
from ai.lexical import ingest_lexical
from data.db import get_conn

MANIFEST = Path(__file__).resolve().parents[1] / "data" / "seeds" / "procedure_urls.txt"
_LINE = re.compile(r"^(https?://\S+)\s*(?:#\s*(.*))?$")
_LANG = re.compile(r"(?:^|\s)lang=(ar|fr|en)(?:\s|$)")


@dataclass(frozen=True)
class ManifestEntry:
    url: str
    lang: str | None


def parse_manifest(text: str) -> list[ManifestEntry]:
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _LINE.match(line)
        if not match:
            raise ValueError(f"invalid manifest line {number}")
        url, comment = match.group(1), match.group(2) or ""
        if url in seen:
            raise ValueError(f"duplicate manifest URL on line {number}")
        lang_match = _LANG.search(comment)
        entries.append(ManifestEntry(url, lang_match.group(1) if lang_match else None))
        seen.add(url)
    if not entries:
        raise ValueError("procedure manifest is empty")
    return entries


def existing_urls() -> set[str]:
    with get_conn() as conn:
        return {row["url"] for row in conn.execute("SELECT DISTINCT url FROM procedures")}


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    unknown = [arg for arg in args if arg != "--refresh"]
    if unknown:
        print("usage: python -m ai.ingest_manifest [--refresh]")
        return 2
    refresh = "--refresh" in args
    entries = parse_manifest(MANIFEST.read_text(encoding="utf-8"))
    present = existing_urls()
    inserted = skipped = 0
    failed: list[str] = []

    for entry in entries:
        if not refresh and entry.url in present:
            print(f"PRESENT {entry.url}")
            skipped += 1
            continue
        try:
            chunks = ingest_url(entry.url, entry.lang)
        except Exception as exc:
            # An embedding quota/outage must not make a verified page disappear.
            # Store it with a NULL vector and search that subset lexically until
            # a later --refresh succeeds semantically.
            try:
                chunks = ingest_lexical(entry.url, entry.lang)
            except Exception:
                chunks = 0
            if chunks:
                print(f"LOADED* {entry.url} ({chunks} lexical chunks; {type(exc).__name__})")
                inserted += chunks
                continue
            # Never print response bodies, page text, credentials or DB rows.
            print(f"FAILED  {entry.url} ({type(exc).__name__})")
            failed.append(entry.url)
            continue
        if not chunks:
            print(f"FAILED  {entry.url} (nothing fetched/extracted)")
            failed.append(entry.url)
            continue
        print(f"LOADED  {entry.url} ({chunks} chunks)")
        inserted += chunks

    print(f"summary: {len(entries)} URLs; {inserted} chunks loaded; "
          f"{skipped} already present; {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

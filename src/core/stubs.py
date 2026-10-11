"""Canned implementations so the app runs before real modules land.
As B and D ship real code, `providers.py` auto-swaps these out.
Do NOT build features here — this only keeps the pipeline green."""
from __future__ import annotations
from typing import Optional
from shared.contracts import (
    Doc, Source, Facility, DrugRecord, Hotline, Metadata, Lang,
)

HOTLINES = [
    Hotline(name="MoPH hotline", number="1787", purpose="general health info"),
    Hotline(name="Primary care", number="1214", purpose="medication / coverage"),
    Hotline(name="Mental health", number="1564", purpose="mental health support"),
    Hotline(name="Red Cross", number="140", purpose="emergency / ambulance"),
]


class StubLLM:
    name = "stub"

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        return "[stub answer] " + (context[:200] or prompt[:200])

    def classify(self, text: str, labels: list[str]) -> str:
        return labels[0] if labels else "other"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]


class StubTranscriber:
    def transcribe(self, audio: bytes, mime: str) -> tuple[str, Optional[Lang]]:
        return ("[stub transcript of voice note]", None)


class StubProcedureSearch:
    def search(self, query: str, lang: Optional[Lang] = None, k: int = 4) -> list[Doc]:
        return []


class StubDirectory:
    def nearest(self, kind, caza=None, lat=None, lon=None, k=3) -> list[Facility]:
        return []


class StubMedicine:
    def find(self, name: str) -> list[DrugRecord]:
        return []


def stub_redact(text: str) -> str:
    return text


def stub_classify(transcript: str) -> Metadata:
    return Metadata(topic="other", lang=None, outcome="answered", day="2026-10-10")

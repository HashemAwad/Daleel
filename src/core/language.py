"""Deterministic language selection for replies that bypass the LLM."""
from __future__ import annotations

from shared.contracts import Inquiry, Lang


def of(inq: Inquiry) -> Lang:
    if inq.lang:
        return inq.lang
    try:
        from ai.classifier import detect_lang
        return detect_lang(inq.text) or "en"
    except Exception:
        return "en"

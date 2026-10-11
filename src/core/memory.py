"""Bounded, temporary per-session conversation state. Owner: A.

DEMO-GRADE: in-process dict, single worker, 5-min TTL. A multi-worker deployment
must move this behind a shared store (Postgres/Redis) keyed by the anonymous
session reference and use the same retention policy.
"""
from __future__ import annotations
import time
from typing import Optional

_TTL_SECONDS = 300.0
_pending_town: dict[str, tuple[str, float]] = {}
_last_directory_kind: dict[str, tuple[str, float]] = {}
_conversation_context: dict[str, tuple[dict, float]] = {}
_conversation_history: dict[str, tuple[list[dict[str, str]], float]] = {}
_MAX_HISTORY_MESSAGES = 8
_MAX_MESSAGE_CHARS = 1200


def remember_pending_town(user_ref: str, original_text: str) -> None:
    _pending_town[user_ref] = (original_text, time.monotonic())


def take_pending_town(user_ref: str) -> Optional[str]:
    """Pop and return the question we asked a town for, if still fresh."""
    item = _pending_town.pop(user_ref, None)
    if not item:
        return None
    text, ts = item
    return text if (time.monotonic() - ts) <= _TTL_SECONDS else None


def remember_directory_kind(user_ref: str, kind: str) -> None:
    """Remember whether the user was looking at hospitals, pharmacies or PHCs."""
    _last_directory_kind[user_ref] = (kind, time.monotonic())


def last_directory_kind(user_ref: str) -> Optional[str]:
    item = _last_directory_kind.get(user_ref)
    if not item:
        return None
    kind, ts = item
    if (time.monotonic() - ts) > _TTL_SECONDS:
        _last_directory_kind.pop(user_ref, None)
        return None
    return kind


def remember_context(user_ref: str, context: dict) -> None:
    """Remember only structured routing state—never message text or model prose."""
    clean = {k: v for k, v in context.items()
             if k in {"tool", "facility_type", "caza", "drug"} and v}
    if clean:
        _conversation_context[user_ref] = (clean, time.monotonic())


def last_context(user_ref: str) -> dict:
    item = _conversation_context.get(user_ref)
    if not item:
        return {}
    context, ts = item
    if (time.monotonic() - ts) > _TTL_SECONDS:
        _conversation_context.pop(user_ref, None)
        return {}
    return dict(context)


def remember_turn(user_ref: str, user_text: str, assistant_text: str) -> None:
    """Append one redacted exchange to bounded short-term history."""
    now = time.monotonic()
    item = _conversation_history.get(user_ref)
    messages = list(item[0]) if item and (now - item[1]) <= _TTL_SECONDS else []
    messages.extend([
        {"role": "user", "content": user_text[:_MAX_MESSAGE_CHARS]},
        {"role": "assistant", "content": assistant_text[:_MAX_MESSAGE_CHARS]},
    ])
    _conversation_history[user_ref] = (messages[-_MAX_HISTORY_MESSAGES:], now)


def conversation_history(user_ref: str) -> list[dict[str, str]]:
    item = _conversation_history.get(user_ref)
    if not item:
        return []
    messages, ts = item
    if (time.monotonic() - ts) > _TTL_SECONDS:
        _conversation_history.pop(user_ref, None)
        return []
    return [dict(message) for message in messages]

"""Tiny per-session memory for follow-ups. Owner: A.

Only remembers one thing: when we had to ask the user for a town (a directory
question with no location), we stash the original question so their next message
("Beirut") completes it instead of starting over.

DEMO-GRADE: in-process dict, single worker, 5-min TTL. Phase 2 (multi-worker
deployment) must move this to a shared store (e.g. Redis) keyed by session.
"""
from __future__ import annotations
import time
from typing import Optional

_TTL_SECONDS = 300.0
_pending_town: dict[str, tuple[str, float]] = {}
_last_directory_kind: dict[str, tuple[str, float]] = {}


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

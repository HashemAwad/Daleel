"""Pseudonymous user refs. Owner: C.

A raw phone number must never reach the pipeline, the database, or a log line.
Channels hash it here once, at the edge, and pass only the hash onwards as
`Inquiry.user_ref` (see shared.contracts).

HMAC-SHA256 with a server-side salt: same phone -> same ref (so a conversation
hangs together), and the ref cannot be reversed to a number. Rotating
SESSION_HASH_SALT makes old refs unlinkable to new ones, which is what we want
for the retention story.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import secrets

from shared.config import settings

log = logging.getLogger("daleel.channels")

_WEAK_SALTS = {"", "change-me"}


def salt_is_weak() -> bool:
    """True when .env still has the placeholder salt. Surfaced on /health/channels
    so nobody demos (or deploys) with a guessable salt."""
    return settings.session_hash_salt in _WEAK_SALTS


def user_ref(raw_id: str, prefix: str = "wa") -> str:
    """Salted hash of a channel identity (phone number, web session token).

    `prefix` keeps channels in separate namespaces so a WhatsApp ref and a web
    ref can never collide.
    """
    digest = hmac.new(
        settings.session_hash_salt.encode("utf-8"),
        raw_id.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{prefix}_{digest[:32]}"


def new_web_session() -> str:
    """A fresh opaque web session id. Random, so it carries no PII at all;
    still hashed through user_ref() so core sees one consistent ref format."""
    return user_ref(secrets.token_urlsafe(24), prefix="web")

"""Channel-only env vars. Owner: C.

`shared/config.py` is A's file and the shared contract, so these channel-local
knobs live here instead of forcing a shared-file change mid-sprint. If any of
them turns out to matter to another module, move it to shared/config.py with
A's +1 and delete it from here.
"""
from __future__ import annotations

import os


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class ChannelSettings:
    # Fail closed on an unverifiable webhook. Leave false locally (no Twilio
    # token yet), set true wherever the webhook is publicly reachable.
    require_twilio_signature = _flag("REQUIRE_TWILIO_SIGNATURE")

    # Twilio also posts AccountSid with every webhook; env is the fallback for
    # authenticating media downloads.
    twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()

    # "join <two-words>" — the Twilio sandbox pairing code, shown on /join.
    sandbox_join_code = os.getenv("TWILIO_SANDBOX_JOIN_CODE", "").strip()


channel_settings = ChannelSettings()

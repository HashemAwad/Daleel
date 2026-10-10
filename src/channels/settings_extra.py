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

    # --- Meta WhatsApp Cloud API (second provider; see whatsapp_meta.py) ---
    # Twilio's trial blocks inbound webhooks entirely, so Meta's free test
    # number is the path to a live WhatsApp demo. Both handlers coexist.
    meta_app_secret = os.getenv("WHATSAPP_APP_SECRET", "").strip()
    meta_access_token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    meta_phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    # We echo this back to Meta on the GET verification handshake.
    meta_verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
    meta_graph_version = os.getenv("WHATSAPP_GRAPH_VERSION", "v21.0").strip()
    require_meta_signature = _flag("REQUIRE_META_SIGNATURE")

    @property
    def meta_configured(self) -> bool:
        return bool(self.meta_access_token and self.meta_phone_number_id)


channel_settings = ChannelSettings()

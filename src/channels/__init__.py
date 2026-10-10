"""Channels package. Owner: C.

`register(app)` mounts every channel router onto A's FastAPI app. `core/app.py`
calls it, so the whole service — core, web widget, dashboard, both WhatsApp
webhooks — is served by:

    PYTHONPATH=src uvicorn core.app:app --reload

register() stays idempotent, and `channels/asgi.py` still composes the same app
independently. Both exist as a fallback for the case where core's registration
is reverted or an owner wants to run the channel surface alone.
"""
from __future__ import annotations

from typing import Any

__all__ = ["register"]


_FLAG = "daleel_channels_registered"


def _paths(routes: Any) -> set[str]:
    """Every path reachable under `routes`.

    Newer FastAPI keeps an included router nested instead of flattening its
    routes into app.routes, so we recurse into whatever wrapper we find.
    """
    found: set[str] = set()
    for route in routes or ():
        path = getattr(route, "path", None)
        if isinstance(path, str) and path:
            found.add(path)
        nested = getattr(route, "original_router", None) or getattr(route, "included_router", None)
        if nested is not None:
            found |= _paths(getattr(nested, "routes", ()))
    return found


def register(app: Any) -> list[str]:
    """Include the channel routers once each. Returns the paths it added.

    Safe to call twice: a flag on app.state plus a path check keeps a second
    call (e.g. core/app.py and channels/asgi.py both calling it) a no-op.
    """
    if getattr(app.state, _FLAG, False):
        return []

    # imported here, not at package import time, so `from channels import x`
    # inside these modules can never hit a half-initialised package
    from channels import metrics, qr, web, whatsapp, whatsapp_meta

    added: list[str] = []
    for router in (web.router, metrics.router, qr.router, whatsapp.router, whatsapp_meta.router):
        router_paths = _paths(router.routes)
        if router_paths & _paths(app.routes):
            continue  # already mounted by someone else
        app.include_router(router)
        added.extend(sorted(router_paths))

    # Load Whisper when the server starts (a TestClient built without `with` never does),
    # so a missing model is an ERROR line at boot, not a string of "couldn't read" replies,
    # and the first voice note does not pay the load time inside Twilio's 15 seconds.
    app.router.on_startup.append(_warm_voice)

    setattr(app.state, _FLAG, True)
    return added


def _warm_voice() -> None:
    import threading

    from core import providers

    ready = getattr(providers.transcriber, "ready", None)
    if ready:
        threading.Thread(target=ready, daemon=True, name="whisper-warmup").start()

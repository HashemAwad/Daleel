"""Composed ASGI app: core + channels. Owner: C.

core/app.py now calls `register(app)` itself, so the normal entry point serves
everything. This module stays as a fallback for the case where that call is
reverted, or when running the channel surface on its own:

    PYTHONPATH=src uvicorn core.app:app --reload        # the normal way
    PYTHONPATH=src uvicorn channels.asgi:app --reload   # fallback, this module

It mounts nothing of its own — it imports A's app untouched and adds the
channel routers, so both entry points serve the same application.
"""
from __future__ import annotations

from core.app import app  # noqa: F401  (re-exported as the ASGI target)

from channels import register

register(app)

"""Composed ASGI app: core + channels. Owner: C.

Run this instead of `core.app:app` until A adds the one-line
`from channels import register; register(app)` to core/app.py:

    PYTHONPATH=src uvicorn channels.asgi:app --reload

It mounts nothing of its own — it imports A's app untouched and adds the
channel routers, so both entry points serve the same application.
"""
from __future__ import annotations

from core.app import app  # noqa: F401  (re-exported as the ASGI target)

from channels import register

register(app)

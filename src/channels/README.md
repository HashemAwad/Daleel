# /src/channels — Member C (channels & frontend)

Your folder (+ `/web`). Build a FastAPI router and include it from `core/app.py`
(coordinate the one-line `app.include_router(...)` with A).

| File | Does |
|------|------|
| `whatsapp.py` | Twilio webhook `POST /webhook/whatsapp`; verify signature; normalise to `Inquiry`; download voice notes → set `audio_url`; call `pipeline.handle`; reply via Twilio |
| `web.py` | `POST /chat` already exists in core; add anything the widget needs (e.g. session ids) |
| `../web/index.html` | RTL chat widget calling `/chat` |
| `../web/dashboard.html` | Phase-2 stub reading the metadata table |

Build `Inquiry` with a **salted-hash** `user_ref` (never raw phone). Full ticket: `docs/tickets/dev-c.md`.

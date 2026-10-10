# /src/channels — Member C (channels & frontend)

Turns inbound messages (WhatsApp + web) into an `Inquiry`, calls
`core.pipeline.handle`, and renders the `Answer` back to the channel.

## Files
| File | Does |
|------|------|
| `whatsapp.py` | Twilio webhook `POST /webhook/whatsapp`: verify signature → normalise to `Inquiry` → voice notes downloaded + transcribed here → `pipeline.handle` → TwiML reply |
| `identity.py` | `user_ref()` — HMAC-SHA256 salted hash of a phone/session. **The raw number never leaves this module.** |
| `render.py` | `Answer` → WhatsApp text parts (sources appended, split under the 1600-char limit) |
| `web.py` | `/api/session`, `/api/hotlines`, `/health/channels`, serves `/dashboard` and `/join` |
| `metrics.py` | `/api/metrics` — anonymised aggregates for the Phase-2 dashboard (real `metadata` rows, else mock) |
| `qr.py` | `/api/whatsapp-info`, `/qr.svg` — sandbox join link + QR |
| `settings_extra.py` | Channel-only env vars (kept out of A's `shared/config.py`) |
| `asgi.py` | Dev entry point: A's app + channel routers |
| `../web/index.html` | RTL chat widget → `/chat` |
| `../web/dashboard.html` | Phase-2 dashboard → `/api/metrics` |
| `../web/join.html` | QR + sandbox join instructions |

## Running
Until A adds the one-line include (below), run the composed app:

```bash
PYTHONPATH=src uvicorn channels.asgi:app --reload    # core + channels
PYTHONPATH=src pytest -q
```

`core.app:app` still runs on its own — it just won't have the channel routes.

## The one line for A
`register()` is idempotent, so this is safe to add any time, and
`channels/asgi.py` keeps working afterwards:

```python
# core/app.py, after `app = FastAPI(...)`
from channels import register; register(app)
```

## Privacy rules in this folder
- `Inquiry.user_ref` is **always** `identity.user_ref(...)` — never a raw phone.
- `ProfileName` (the sender's WhatsApp display name) is ignored entirely.
- Logs carry outcomes and lengths only: never message text, transcripts, or audio.
- The dashboard reads only the six `metadata` columns, which hold no free text.

## Env vars this folder reads
Standard (`shared/config.py`): `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`,
`PUBLIC_BASE_URL`, `SESSION_HASH_SALT`, `DATABASE_URL`.

Channel-only (`settings_extra.py`):

| Var | Default | Why |
|-----|---------|-----|
| `REQUIRE_TWILIO_SIGNATURE` | `false` | `true` ⇒ refuse any webhook we can't verify. **Set it wherever the webhook is public.** |
| `TWILIO_ACCOUNT_SID` | — | Fallback auth for media downloads (Twilio also posts `AccountSid`). |
| `TWILIO_SANDBOX_JOIN_CODE` | — | The `join <code>` phrase; shown and encoded in the QR on `/join`. |

Signature handling: with a token set, a bad or missing signature is a **403**.
With no token (fresh `.env`), the request is allowed through and a warning is
logged — local-dev convenience only, which `REQUIRE_TWILIO_SIGNATURE=true`
turns off.

Full ticket: `docs/tickets/dev-c.md`.

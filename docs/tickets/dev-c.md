# Dev C — Channels & frontend

You own `src/channels/` and `web/`. You turn messages (WhatsApp + web) into `Inquiry`, call `pipeline.handle`, and render the `Answer`. **Your independence: total after S0** — A's `/chat` already runs on stubs, so you can build the full UX today and it only gets better as others push.

Branch per ticket: `feat/c/<ID>`. Done = the check passes **and** `PYTHONPATH=src pytest -q` is green.

---
### C0 · Web widget talks to /chat — Sprint 0–1 · **Independent**
`web/index.html` exists and calls `/chat`. Open it against the running backend and confirm a round-trip.
**Done when:** typing a question in `web/index.html` shows the bot's answer (stub answer is fine at S0).

### C1 · RTL + language polish — Sprint 1–2 · **Independent**
Make the widget solid for Arabic RTL, Arabizi, French, English; show source links; add quick-reply buttons ("Another question", "Talk to a person").
**Done when:** an Arabic question renders right-to-left; a reply with a `source` shows a clickable link.

### C2 · WhatsApp webhook — Sprint 2 · **Independent** (needs Twilio sandbox creds in `.env`)
`src/channels/whatsapp.py`: FastAPI router with `POST /webhook/whatsapp`; **verify the Twilio signature**; normalise to `Inquiry` with a **salted-hash** `user_ref` (never the raw phone); call `pipeline.handle`; reply via Twilio. Coordinate ONE line with A to `app.include_router(...)`.
**Done when:** a WhatsApp message to the sandbox gets the bot's reply on your phone.

### C3 · Voice-note intake — Sprint 3 · **Soft-dep on B's transcriber** (stub covers it)
When a WhatsApp message has media audio, download the bytes and set them on the inquiry path so `providers.transcriber` runs (stub until B ships, then real). Keep raw audio out of logs.
**Done when:** sending a voice note returns a text answer (placeholder text while on the stub; real once B's `TranscriberImpl` lands — no code change needed on your side).

### C4 · Phase-2 dashboard stub — Sprint 5 · **Soft-dep on D's metadata rows** (render mock until real)
`web/dashboard.html` (+ a read endpoint via A if needed): show top topics, unanswered count, language mix, escalation rate from the `metadata` table.
**Done when:** the page renders counts; works on mock data now, real metadata once D's retention job runs.

### C5 · Demo polish + QR — Sprint 5–6 · **Independent**
QR code to join the Twilio sandbox; tidy styling; make the web widget the reliable fallback if WhatsApp fails on stage.
**Done when:** a judge scans the QR and sends a message end-to-end; web widget works offline-of-Twilio.

**Agent kickoff prompt:**
> You are working ONLY in `src/channels/` and `web/` of the Daleel repo. Read `CLAUDE.md`, `docs/CONTRACTS.md`, and `docs/tickets/dev-c.md`. Implement ticket C<N>. Build `Inquiry` objects per `shared.contracts` with a salted-hash `user_ref` (never a raw phone number); never log message text or audio. Call `core.pipeline.handle`. Coordinate only the single `include_router` line with A. Run `PYTHONPATH=src pytest -q`; keep it green.

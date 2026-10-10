# Dev A — Backend core & orchestration

You own `src/core/`, `src/app`, and you **steward** `src/shared/contracts.py`. You are the composition root: everyone integrates through your `providers.py`, which already runs on stubs. **Your independence: total after S0** — your module already works end-to-end on stubs; you upgrade pieces in place.

Branch per ticket: `feat/a/<ID>`. Done = the check passes **and** `PYTHONPATH=src pytest -q` is green.

---
### A0 · Freeze & publish contracts  — Sprint 0 · **Independent (you are the source)**
Confirm `src/shared/contracts.py` matches `docs/CONTRACTS.md`; announce "contracts frozen" in the channel. This unblocks everyone.
**Done when:** teammates can `from shared.contracts import Inquiry, Answer` and the smoke test passes.

### A1 · Runnable app + /chat + /health — Sprint 0–1 · **Independent**
Already scaffolded. Verify it boots and returns an `Answer`.
**Done when:** `PYTHONPATH=src uvicorn core.app:app` serves; `curl -s localhost:8000/chat -H 'content-type: application/json' -d '{"text":"how do I get my cancer medicine?","user_ref":"t"}'` returns JSON with `text` + `tool`.

### A2 · Real LLM client — Sprint 1 · **Independent** (needs only `ANTHROPIC_API_KEY`)
Flesh out `core/llm.py` (`AnthropicLLM`). It's wired already; set the key in `.env` and confirm real answers replace the `[stub answer]` prefix.
**Done when:** with a key set, `/chat` returns a fluent grounded answer; with no key, it still falls back to stub (don't break that).

### A3 · Grounding gate + fallback — Sprint 1–2 · **Independent**
Harden `pipeline.handle`: answer only from `ToolResult`; if `result.is_empty()`, return the 1787 fallback with `grounded=False, outcome="unanswered"`. Add a cheap check that the answer text doesn't invent sources.
**Done when:** a nonsense query ("price of unicorn tears") returns the fallback, `grounded=False`; a real query returns `grounded=True` with a source.

### A4 · Tool router upgrade to LLM tool-calling — Sprint 2–3 · **Independent**
Replace keyword routing in `router.py` with Claude tool-use (one tool per question type) once the keyword version demos. Keep the keyword router as fallback.
**Done when:** the 7 user-story prompts in the scope doc each hit the right tool (add them to `tests/test_router.py`).

### A5 · Safety rules solid — Sprint 3 · **Independent**
Expand `core/safety.py` emergency + advice lists (AR/arabizi/FR/EN) using B's eval findings. Emergency fires before everything.
**Done when:** `test_emergency_shortcircuits` and `test_medical_advice_refused` pass for AR and EN variants you add.

### A6 · Wire voice + redaction integration points — Sprint 3 · **Soft-dep on B** (stubs cover it)
Ensure the pipeline calls `providers.transcriber` (when `inq.audio_url`/audio present) and `providers.redact` before the model. Works on stubs today; flips to real automatically when B pushes.
**Done when:** an inquiry with audio runs through transcription→pipeline; redaction is applied before `llm.generate` (assert in a test with a fake redactor).

### A7 · Integration pass + demo endpoints — Sprint 4–5 · **Soft-dep on all** (stubs cover gaps)
Keep `providers.py` names stable; add `/metadata` read-only endpoint for C's dashboard if needed; help each dev's real module light up.
**Done when:** with B+D merged, `/chat` answers all 4 question types from real data; pytest green.

**Agent kickoff prompt:**
> You are working ONLY in `src/core/` and `src/shared/` of the Daleel repo. Read `CLAUDE.md`, `docs/CONTRACTS.md`, and `docs/tickets/dev-a.md`. Implement ticket A<N>. Keep `core/providers.py` import names stable. Never edit another module's folder. Run `PYTHONPATH=src pytest -q` before you finish; it must stay green.

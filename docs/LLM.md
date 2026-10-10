# LLM backends — bridge now, self-host later

The answer model is pluggable (`core/providers.py` picks it from `.env`), so we
can **build now on a free hosted model** and **switch to the self-hosted one**
with a one-line change when its download finishes. Nothing we build changes.

The model only *phrases* answers — the facts always come from our database/retrieval
and redaction always runs first. So the backend is swappable without touching anything else.

## Three backends (set `DALEEL_MODEL_PROVIDER`)
| Provider | When | Needs | Notes |
|----------|------|-------|-------|
| `hosted` | **now (bridge)** | a free API key, no download | fluent immediately; data leaves the machine (dev only) |
| `selfhost` | **final** | `ollama pull qwen2.5:7b` done | private, on-device; the production target |
| `anthropic` | not used | paid key | left in for completeness |

If the configured backend is unavailable, the app still answers from the data
(plain/templated) — it never hard-fails.

## Bridge mode (use while qwen downloads) — Groq, free
1. Create a free key at **https://console.groq.com** → API Keys → Create (no card).
2. In `.env`:
   ```
   DALEEL_MODEL_PROVIDER=hosted
   DALEEL_MODEL=llama-3.3-70b-versatile
   DALEEL_LLM_BASE_URL=https://api.groq.com/openai/v1
   DALEEL_LLM_API_KEY=gsk_...          # your key
   ```
3. Restart the server. Answers are now fluent (Llama 3.3 70B, good Arabic).

Any OpenAI-compatible endpoint works here (OpenRouter, Together, …) — just change
`DALEEL_LLM_BASE_URL`, `DALEEL_LLM_API_KEY`, `DALEEL_MODEL`.

## Switch to self-hosted (when `ollama list` shows qwen2.5:7b)
Change two lines in `.env` and restart:
```
DALEEL_MODEL_PROVIDER=selfhost
DALEEL_MODEL=qwen2.5:7b
```
That's the whole switch. This is the private, on-device production model.

## Privacy note
In `hosted` mode the (redacted) text is sent to the provider — fine for development,
**not** for production. The ministry-facing deployment uses `selfhost`, where nothing
leaves the server. We redact phone numbers / IDs / names before *any* model call in both modes.

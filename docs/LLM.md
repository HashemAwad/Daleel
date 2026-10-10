# LLM backends — bridge now, self-host later

The answer model is pluggable (`core/providers.py` picks it from `.env`). Build
on a hosted model now, then prefer the self-hosted model when it is installed.
When `selfhost` is selected, the configured hosted endpoint remains an automatic
runtime fallback if Ollama is missing or a local generation fails.

The model only *phrases* answers — the facts always come from our database/retrieval
and redaction always runs first. So the backend is swappable without touching anything else.

## Three backends (set `DALEEL_MODEL_PROVIDER`)
| Provider | When | Needs | Notes |
|----------|------|-------|-------|
| `hosted` | **now (bridge)** | a free API key, no download | fluent immediately; data leaves the machine (dev only) |
| `selfhost` | **demo/local** | `ollama pull qwen2.5:7b` done | private, on-device; hosted remains its automatic fallback |
| `anthropic` | not used | paid key | left in for completeness |

If the configured backend is unavailable, the app still answers from the data
(plain/templated) — it never hard-fails.

## Final decision

1. **Best hosted-demo balance:** Google `gemini-3.6-flash`. It produced a
   complete grounded Arabic answer in roughly 2.5 seconds in the demo environment;
   3.8 Flash's reasoning behavior was materially slower for this short-answer UI.
2. **Hosted reliability fallback:** Groq `llama-3.3-70b-versatile` when Gemini
   quota is unavailable. Groq lists it as a production model.
3. **Self-hosted demo target:** Ollama `qwen2.5:7b`. Its download was already
   halfway complete when this decision was reviewed, so finishing and testing it
   is lower risk than restarting a large download hours before the demo.
4. **No-model fallback:** Daleel renders retrieved facts directly, so a model
   outage never removes verified facility, medicine or procedure results.

The model is never allowed to choose facts. Safety, routing, retrieval, distance
ranking and grounding remain deterministic.

## Hosted mode — choose the available account

**Gemini (best answer quality for the demo):**
```
DALEEL_HOSTED_MODEL=gemini-3.6-flash
DALEEL_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
DALEEL_LLM_API_KEY=...                 # key from aistudio.google.com/app/apikey
```

**Groq (reliable backup — fast and production-listed):**
1. Free key at **https://console.groq.com** → API Keys → Create (no card).
2. In `.env`:
   ```
   DALEEL_MODEL_PROVIDER=hosted
   DALEEL_HOSTED_MODEL=llama-3.3-70b-versatile
   DALEEL_LLM_BASE_URL=https://api.groq.com/openai/v1
   DALEEL_LLM_API_KEY=gsk_...          # your Groq key
   ```
3. Restart the server → fluent answers (Llama 3.3 70B, good Arabic).

Gemini is the quality-first choice; Groq is the quota/reliability choice. Do not
switch providers without running the same multilingual evaluation set.

> "OpenAI-format" = the de-facto API shape Gemini/Groq/OpenRouter all accept — **not**
> OpenAI the company. The client (`core/llm_hosted.py`) retries transient 429/503s;
> a persistent provider failure falls back to plain (still accurate) answers, never an error.

## Switch to self-hosted (when `ollama list` shows `qwen2.5:7b`)
Keep separate names for the local and hosted models, then change the provider and restart:
```
DALEEL_MODEL_PROVIDER=selfhost
DALEEL_LOCAL_MODEL=qwen2.5:7b
DALEEL_HOSTED_MODEL=gemini-3.6-flash
```
The separate variables matter: if local generation fails, the hosted fallback
must retain its own Gemini/Groq model name rather than receiving the Ollama tag.

### Post-demo upgrade: Qwen3 8B

Qwen3 8B has broader multilingual training, including Standard and Levantine
Arabic, and should be evaluated after the hackathon. We are intentionally not
discarding the current half-complete download during the demo build. This is a
schedule-risk decision, not a claim that Qwen2.5 is the stronger model. Compare
both on the same reviewed evaluation set before changing production.

## Privacy note
In `hosted` mode the (redacted) text is sent to the provider — fine for development,
**not** for production. The ministry-facing deployment uses `selfhost`, where nothing
leaves the server. We redact phone numbers / IDs / names before *any* model call in both modes.

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
| `selfhost` | **demo/local** | `ollama pull qwen3.5:9b` done | private, on-device; hosted remains its automatic fallback |
| `anthropic` | not used | paid key | left in for completeness |

If the configured backend is unavailable, the app still answers from the data
(plain/templated) — it never hard-fails.

## Final decision

1. **Best hosted-demo balance:** Google `gemini-3.6-flash`. It produced a
   complete grounded Arabic answer in roughly 2.5 seconds in the demo environment;
   3.8 Flash's reasoning behavior was materially slower for this short-answer UI.
2. **Hosted reliability fallback:** Groq `llama-3.3-70b-versatile` when Gemini
   quota is unavailable. Groq lists it as a production model.
3. **Self-hosted demo target:** Ollama `qwen3.5:9b` (current generation). Chosen
   over qwen2.5:7b for noticeably stronger Arabic/Arabizi and instruction-following
   (grounding), at ~6.6GB it fits 24GB with headroom, and it has native tool
   calling. Downloaded and verified: fluent grounded Arabic answers locally.
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

## Switch to self-hosted (when `ollama list` shows `qwen3.5:9b`)
Keep separate names for the local and hosted models, then change the provider and restart:
```
DALEEL_MODEL_PROVIDER=selfhost
DALEEL_LOCAL_MODEL=qwen3.5:9b
DALEEL_HOSTED_MODEL=gemini-3.6-flash
```
The separate variables matter: if local generation fails, the hosted fallback
must retain its own Gemini/Groq model name rather than receiving the Ollama tag.

### Larger models (post-demo evaluation)

`qwen3.5:9b` is the demo model. If more capacity is available post-hackathon,
evaluate larger options on the same reviewed eval set before changing production:
`qwen3.5:9b-q8_0` (near-lossless, ~11GB), or Arabic-specialist models such as
Fanar-2-27B / Jais-30B (strongest pure Arabic, but ~16-20GB and weaker on
French/English/Arabizi, so not ideal as a single all-cases model).

## Privacy note
In `hosted` mode the (redacted) text is sent to the provider — fine for development,
**not** for production. The ministry-facing deployment uses `selfhost`, where nothing
leaves the server. We redact phone numbers / IDs / names before *any* model call in both modes.

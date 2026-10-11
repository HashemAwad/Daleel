# LLM runtime — API only

Daleel uses an external model API. The deployed application never starts,
selects, or falls back to Ollama or another locally/self-hosted model.

The model interprets the request and phrases grounded results. Facts still come
from Daleel's verified procedure, medicine, facility, and hotline data. Personal
identifiers are redacted before an API request.

## Primary API: Claude

Configure `.env`:

```env
DALEEL_MODEL_PROVIDER=api
DALEEL_API_VENDOR=anthropic
DALEEL_ANTHROPIC_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=... # never commit this value
```

Claude is used both for schema-constrained message understanding and for
phrasing answers grounded in Daleel's retrieved records. Structured
understanding is implemented as a forced Claude tool call, so switching from
Gemini does not reintroduce keyword routing or one-off classification fixes.

To select Gemini explicitly, set `DALEEL_API_VENDOR=gemini` and configure
`DALEEL_HOSTED_MODEL`, `DALEEL_LLM_BASE_URL`, and `DALEEL_LLM_API_KEY`.

Restart the application after changing environment variables. The response's
`model` field identifies the API/model that actually answered.

## Optional API backup

A second, independent API provider avoids losing natural-language understanding
when Gemini is rate-limited or unavailable. This is API-to-API failover—not a
local model fallback.

Example using Groq:

```env
DALEEL_BACKUP_HOSTED_MODEL=llama-3.3-70b-versatile
DALEEL_BACKUP_LLM_BASE_URL=https://api.groq.com/openai/v1
DALEEL_BACKUP_LLM_API_KEY=... # never commit this value
```

If neither API is available, Daleel does not invent an answer, does not run
legacy keyword routing, and does not call a local LLM. It returns an explicit
temporary-unavailability response.

## Reliability and quota

No usage-limited public API can guarantee unlimited availability. For the demo:

1. Keep prepaid Claude credit available and monitor it in Anthropic Console.
2. Configure an independent API backup with a separate provider and quota.
3. Keep retries bounded so a provider outage does not stall the chat.
4. Run the multilingual evaluation set against the exact production model before
   changing providers.

The term `HostedLLM` in Python means an external API client. It does not mean
self-hosting. The legacy provider value `hosted` remains accepted for old `.env`
files; new configuration must use `api`.

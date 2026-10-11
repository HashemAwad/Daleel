# LLM runtime — API only

Daleel uses an external model API. The deployed application never starts,
selects, or falls back to Ollama or another locally/self-hosted model.

The model interprets the request and phrases grounded results. Facts still come
from Daleel's verified procedure, medicine, facility, and hotline data. Personal
identifiers are redacted before an API request.

## Primary API: Gemini

Configure `.env`:

```env
DALEEL_MODEL_PROVIDER=api
DALEEL_HOSTED_MODEL=gemini-3.6-flash
DALEEL_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta
DALEEL_LLM_API_KEY=... # never commit this value
```

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

If neither API is available, Daleel does not invent an answer and does not call
a local LLM. It can still render facts returned by its verified data tools in a
plain format.

## Reliability and quota

No usage-limited public API can guarantee unlimited availability. For the demo:

1. Use a paid/quota-enabled Gemini project if available.
2. Configure an independent API backup with a separate provider and quota.
3. Keep retries bounded so a provider outage does not stall the chat.
4. Run the multilingual evaluation set against the exact production model before
   changing providers.

The term `HostedLLM` in Python means an external API client. It does not mean
self-hosting. The legacy provider value `hosted` remains accepted for old `.env`
files; new configuration must use `api`.

"""Hosted LLMClient over any OpenAI-format chat API. Owner: A.

NOT OpenAI the company — "OpenAI-format" is just the de-facto request shape that
Google Gemini, Groq, OpenRouter, etc. all accept. We use Google Gemini (free,
strong Arabic). Behind the same LLMClient Protocol, so switching to self-hosted
qwen is a one-line .env change. Redaction still runs before any call.

Selected when DALEEL_MODEL_PROVIDER=hosted. Config (see docs/LLM.md):
  DALEEL_LLM_BASE_URL   https://generativelanguage.googleapis.com/v1beta/openai   (Gemini)
  DALEEL_LLM_API_KEY    free key from https://aistudio.google.com/app/apikey
  DALEEL_MODEL          gemini-2.0-flash
"""
from __future__ import annotations
import time
import httpx
from shared.config import settings

_RETRY_STATUS = {429, 500, 502, 503, 504}   # transient: overloaded / rate-limited


class HostedLLM:
    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None) -> None:
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.model = model or settings.model

    @classmethod
    def available(cls) -> bool:
        return bool(settings.llm_base_url and settings.llm_api_key)

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        user = f"Context:\n{context}\n\nUser question:\n{prompt}" if context else prompt
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last: Exception | None = None
        for attempt in range(4):          # retry transient overload/rate-limit
            try:
                r = httpx.post(self.base_url + "/chat/completions", timeout=60,
                               headers=headers, json=payload)
                if r.status_code in _RETRY_STATUS:
                    last = httpx.HTTPStatusError(f"{r.status_code}", request=r.request, response=r)
                    time.sleep(1.0 * (attempt + 1))
                    continue
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            except (httpx.TransportError, httpx.TimeoutException) as e:
                last = e
                time.sleep(1.0 * (attempt + 1))
        raise last or RuntimeError("hosted LLM unavailable")

    def classify(self, text: str, labels: list[str]) -> str:
        out = self.generate(
            "Classify the text into exactly one label. Reply with the label only.",
            f"Labels: {', '.join(labels)}\n\nText: {text}",
        ).strip().lower()
        for lb in labels:
            if lb.lower() in out:
                return lb
        return labels[0] if labels else "other"

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Use the ai/retrieval embedder for embeddings.")

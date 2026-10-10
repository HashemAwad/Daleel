"""Hosted LLMClient over any OpenAI-compatible chat API (Groq, OpenRouter, etc.).
Owner: A.

This is the BRIDGE backend: it gives fluent answers immediately with no model
download, so the team can build while the self-hosted model downloads. Behind
the same LLMClient Protocol, so switching to self-hosted qwen is a one-line .env
change (DALEEL_MODEL_PROVIDER=selfhost). Redaction still runs before any call.

Selected when DALEEL_MODEL_PROVIDER=hosted. Config:
  DALEEL_LLM_BASE_URL   e.g. https://api.groq.com/openai/v1
  DALEEL_LLM_API_KEY    the provider's free API key
  DALEEL_MODEL          the hosted model id, e.g. llama-3.3-70b-versatile
"""
from __future__ import annotations
import httpx
from shared.config import settings


class OpenAICompatLLM:
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
        r = httpx.post(
            self.base_url + "/chat/completions",
            timeout=60,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

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

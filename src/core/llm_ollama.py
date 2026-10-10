"""Free, local LLMClient via Ollama (no API key, runs on your machine). Owner: A.

This is the self-hosted path from the scope doc. Behind the same LLMClient
Protocol as AnthropicLLM, so nothing else changes. Selected when
DALEEL_MODEL_PROVIDER=selfhost in .env. If Ollama isn't running,
providers.py falls back to the stub so the app still boots.

Setup:
  1. install Ollama (https://ollama.com)
  2. `ollama pull qwen2.5:7b`
  3. in .env: DALEEL_MODEL_PROVIDER=selfhost
              DALEEL_LOCAL_MODEL=qwen2.5:7b
"""
from __future__ import annotations
import httpx
from shared.config import settings


class OllamaLLM:
    def __init__(self, model: str | None = None, url: str | None = None) -> None:
        self.model = model or settings.local_model
        self.url = (url or settings.ollama_url).rstrip("/")

    @classmethod
    def available(cls, url: str | None = None) -> bool:
        """Ollama is usable only when it is up and the configured model exists."""
        base = (url or settings.ollama_url).rstrip("/")
        try:
            r = httpx.get(base + "/api/tags", timeout=1.5)
            r.raise_for_status()
            wanted = settings.local_model.split(":latest", 1)[0]
            return any(
                str(m.get("name", "")).split(":latest", 1)[0] == wanted
                for m in r.json().get("models", [])
            )
        except Exception:
            return False

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        user = f"Context:\n{context}\n\nUser question:\n{prompt}" if context else prompt
        r = httpx.post(
            self.url + "/api/chat",
            timeout=120,
            json={
                "model": self.model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
        )
        r.raise_for_status()
        return r.json()["message"]["content"]

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
        # Embeddings are B's job (bge-m3 in ai/retrieval). Not done here.
        raise NotImplementedError("Use the ai/retrieval embedder for embeddings.")

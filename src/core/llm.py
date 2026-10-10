"""LLMClient implementation over the Anthropic API. Owner: A.
Behind the LLMClient Protocol so a self-hosted model is a drop-in later.
If ANTHROPIC_API_KEY is unset, providers.py uses StubLLM instead."""
from __future__ import annotations
import anthropic
from shared.config import settings


class AnthropicLLM:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.model

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        user = f"Context:\n{context}\n\nUser question:\n{prompt}" if context else prompt
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def classify(self, text: str, labels: list[str]) -> str:
        system = "Classify the text into exactly one label. Reply with the label only."
        prompt = f"Labels: {', '.join(labels)}\n\nText: {text}"
        out = self.generate(system, prompt).strip().lower()
        for lb in labels:
            if lb.lower() in out:
                return lb
        return labels[0] if labels else "other"

    def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic has no embeddings endpoint; B wires a real embedder (e.g. bge-m3).
        raise NotImplementedError("Use ai/retrieval embedder for embeddings.")

"""External-API failover wrapper used by the demo deployment.

Both primary and fallback are API clients. This wrapper must never be given an
Ollama/local client. Facts never come from either model.
"""
from __future__ import annotations

from shared.contracts import LLMClient


class FailoverLLM:
    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback
        self.last_used: LLMClient = primary   # which engine served the most recent call

    @property
    def name(self) -> str:
        """Reports the engine that actually answered last (primary or fallback),
        so the debug trail shows whether Gemini or the local model produced the text."""
        who = getattr(self.last_used, "name", type(self.last_used).__name__)
        return f"failover->{who}"

    def _call(self, method: str, *args):
        try:
            out = getattr(self.primary, method)(*args)
            self.last_used = self.primary
            return out
        except Exception:
            out = getattr(self.fallback, method)(*args)
            self.last_used = self.fallback
            return out

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        return self._call("generate", system, prompt, context)

    def classify(self, text: str, labels: list[str]) -> str:
        return self._call("classify", text, labels)

    def generate_structured(self, system: str, prompt: str, schema: dict) -> dict:
        return self._call("generate_structured", system, prompt, schema)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._call("embed", texts)

"""Small LLM failover wrapper used by the demo deployment.

The self-hosted model is preferred for privacy. If it is unavailable at startup
or fails during a request, the configured hosted model phrases the same already-
redacted, retrieved context. Facts never come from either model.
"""
from __future__ import annotations

from shared.contracts import LLMClient


class FailoverLLM:
    def __init__(self, primary: LLMClient, fallback: LLMClient) -> None:
        self.primary = primary
        self.fallback = fallback

    def _call(self, method: str, *args):
        try:
            return getattr(self.primary, method)(*args)
        except Exception:
            return getattr(self.fallback, method)(*args)

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        return self._call("generate", system, prompt, context)

    def classify(self, text: str, labels: list[str]) -> str:
        return self._call("classify", text, labels)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._call("embed", texts)

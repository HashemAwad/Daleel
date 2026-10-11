"""Claude API implementation of Daleel's LLM contract."""
from __future__ import annotations
import json
import anthropic
from shared.config import settings


def _anthropic_schema(value):
    """Translate Gemini's legacy ``nullable`` shape to JSON Schema nulls."""
    if isinstance(value, list):
        return [_anthropic_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    converted = {k: _anthropic_schema(v) for k, v in value.items() if k != "nullable"}
    if value.get("nullable"):
        non_null = dict(converted)
        return {"anyOf": [non_null, {"type": "null"}]}
    return converted


class AnthropicLLM:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = model or settings.anthropic_model

    @classmethod
    def available(cls) -> bool:
        return bool(settings.anthropic_api_key)

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def generate(self, system: str, prompt: str, context: str = "") -> str:
        user = f"Context:\n{context}\n\nUser question:\n{prompt}" if context else prompt
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    def generate_structured(self, system: str, prompt: str, schema: dict) -> dict:
        """Force Claude to submit the requested object as a tool input.

        Tool input is validated against ``input_schema`` by the Claude API. This
        avoids scraping JSON from prose and gives the understanding layer the
        same schema-driven contract it has with Gemini.
        """
        tool_name = "return_structured_result"
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=[{
                "name": tool_name,
                "description": "Return the requested structured result.",
                "input_schema": _anthropic_schema(schema),
            }],
            tool_choice={"type": "tool", "name": tool_name},
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool_name:
                value = block.input
                return value if isinstance(value, dict) else json.loads(value)
        raise RuntimeError("Claude returned no structured tool result")

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

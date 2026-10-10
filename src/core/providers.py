"""Wiring / composition root. Tries real implementations; falls back to stubs.

This is the ONE place core reaches into other modules. As each owner ships
their class, the try-import picks it up with zero changes elsewhere. Keep the
expected class names stable (they are part of the contract):

  B: ai.retrieval.ProcedureSearchImpl
     ai.redaction.redact
     ai.classifier.classify
     ai.transcribe.TranscriberImpl
  D: data.directory.DirectorySearchImpl
     data.medicine.MedicineLookupImpl
  A: core.llm.AnthropicLLM
"""
from __future__ import annotations
from core import stubs

# --- LLM (A) ---
# selfhost (free, Ollama) > anthropic (needs key) > stub (always works).
from shared.config import settings
llm = stubs.StubLLM()
try:
    if settings.model_provider == "selfhost":
        from core.llm_ollama import OllamaLLM
        if OllamaLLM.available():
            llm = OllamaLLM()
    elif settings.model_provider == "hosted":
        from core.llm_hosted import HostedLLM
        if HostedLLM.available():
            llm = HostedLLM()
    elif settings.anthropic_api_key:
        from core.llm import AnthropicLLM
        llm = AnthropicLLM()
except Exception:
    llm = stubs.StubLLM()

# --- Procedure search (B) ---
try:
    from ai.retrieval import ProcedureSearchImpl
    procedures = ProcedureSearchImpl()
except Exception:
    procedures = stubs.StubProcedureSearch()

# --- Directory + medicine (D) ---
try:
    from data.directory import DirectorySearchImpl
    directory = DirectorySearchImpl()
except Exception:
    directory = stubs.StubDirectory()

try:
    from data.medicine import MedicineLookupImpl
    medicine = MedicineLookupImpl()
except Exception:
    medicine = stubs.StubMedicine()

# --- Transcriber (B) ---
try:
    from ai.transcribe import TranscriberImpl
    transcriber = TranscriberImpl()
except Exception:
    transcriber = stubs.StubTranscriber()

# --- redact / classify (B) ---
try:
    from ai.redaction import redact
except Exception:
    redact = stubs.stub_redact

try:
    from ai.classifier import classify
except Exception:
    classify = stubs.stub_classify

HOTLINES = stubs.HOTLINES

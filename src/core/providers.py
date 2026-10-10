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
import logging
from core import stubs

log = logging.getLogger(__name__)

# --- LLM (A) ---
# Preferred order for the demo:
# selfhost (private) -> hosted failover (if configured) -> plain renderer/stub.
from shared.config import settings
llm = stubs.StubLLM()
try:
    if settings.model_provider == "selfhost":
        from core.llm_ollama import OllamaLLM
        from core.llm_hosted import HostedLLM
        local = OllamaLLM() if OllamaLLM.available() else None
        hosted = HostedLLM() if HostedLLM.available() else None
        if local and hosted:
            from core.llm_failover import FailoverLLM
            llm = FailoverLLM(local, hosted)
        elif local:
            llm = local
        elif hosted:
            llm = hosted
    elif settings.model_provider == "hosted":
        from core.llm_hosted import HostedLLM
        if HostedLLM.available():
            llm = HostedLLM()
    elif settings.anthropic_api_key:
        from core.llm import AnthropicLLM
        llm = AnthropicLLM()
except Exception as exc:
    log.error("LLM provider unavailable; using direct renderer: %s", type(exc).__name__)
    llm = stubs.StubLLM()

# --- Procedure search (B) ---
try:
    from ai.retrieval import ProcedureSearchImpl
    procedures = ProcedureSearchImpl()
except Exception as exc:
    log.error("procedure provider unavailable; answers will be withheld: %s", type(exc).__name__)
    procedures = stubs.StubProcedureSearch()

# --- Directory + medicine (D) ---
try:
    from data.directory import DirectorySearchImpl
    directory = DirectorySearchImpl()
except Exception as exc:
    log.error("directory provider unavailable; answers will be withheld: %s", type(exc).__name__)
    directory = stubs.StubDirectory()

try:
    from data.medicine import MedicineLookupImpl
    medicine = MedicineLookupImpl()
except Exception as exc:
    log.error("medicine provider unavailable; answers will be withheld: %s", type(exc).__name__)
    medicine = stubs.StubMedicine()

# --- Transcriber (B) ---
try:
    from ai.transcribe import TranscriberImpl
    transcriber = TranscriberImpl()
except Exception as exc:
    log.error("transcriber unavailable; voice notes disabled: %s", type(exc).__name__)
    transcriber = stubs.StubTranscriber()

# --- redact / classify (B) ---
try:
    from ai.redaction import redact
except Exception as exc:
    log.error("redactor unavailable; hosted model calls remain blocked by deployment checks: %s", type(exc).__name__)
    redact = stubs.stub_redact

try:
    from ai.classifier import classify
except Exception as exc:
    log.error("metadata classifier unavailable: %s", type(exc).__name__)
    classify = stubs.stub_classify

HOTLINES = stubs.HOTLINES

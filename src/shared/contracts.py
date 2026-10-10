"""FROZEN CONTRACTS — the integration spine for Daleel.

Everyone imports from here. Changing a type or an interface signature is a
cross-team event: flag it in the team channel and get a quick +1 before merging,
because it can break another dev's module. Adding a new optional field is safe;
renaming/removing is not.

Owners implement the Protocols; the core pipeline depends only on these
Protocols, so every module can be built and tested with the others stubbed.
"""
from __future__ import annotations

from typing import Literal, Protocol, Optional
from pydantic import BaseModel, Field

# ---- Primitive enums -------------------------------------------------------
Channel = Literal["whatsapp", "web"]
Lang = Literal["ar", "arabizi", "fr", "en"]
Outcome = Literal["answered", "unanswered", "escalated", "refused", "emergency"]
ToolName = Literal["procedure", "directory", "medicine", "hotline", "none"]

# ---- Data models -----------------------------------------------------------
class Source(BaseModel):
    title: str
    url: str
    checked_on: Optional[str] = None  # ISO date we last verified this source


class Doc(BaseModel):
    """A retrieved procedure passage."""
    id: str
    title: str
    content: str
    source: Optional[Source] = None
    lang: Optional[Lang] = None
    score: Optional[float] = None


class Facility(BaseModel):
    id: str
    name: str
    type: str                 # pharmacy | hospital | phc
    caza: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    distance_km: Optional[float] = None


class DrugRecord(BaseModel):
    name: str
    price: Optional[float] = None
    currency: str = "LBP"
    generics: list[str] = Field(default_factory=list)
    is_free: Optional[bool] = None   # free for chronic/incurable list
    list_date: Optional[str] = None


class Hotline(BaseModel):
    name: str
    number: str
    purpose: str


class Inquiry(BaseModel):
    """Normalised inbound message. Channels build this; core consumes it."""
    id: str
    channel: Channel
    text: str = ""
    lang: Optional[Lang] = None
    user_ref: str                     # SALTED HASH of phone/session — never raw PII
    audio_url: Optional[str] = None   # set for voice notes; channels fetch + B transcribes
    lat: Optional[float] = None       # user location (web geolocation / WhatsApp pin) for true
    lon: Optional[float] = None       # distance-based "nearest" — falls back to town when absent


class ToolResult(BaseModel):
    tool: ToolName
    docs: list[Doc] = Field(default_factory=list)
    facilities: list[Facility] = Field(default_factory=list)
    drugs: list[DrugRecord] = Field(default_factory=list)
    hotlines: list[Hotline] = Field(default_factory=list)
    clarification: Optional[Literal["facility_type", "location"]] = None

    def is_empty(self) -> bool:
        return not (self.docs or self.facilities or self.drugs or self.hotlines)


class Answer(BaseModel):
    text: str
    sources: list[Source] = Field(default_factory=list)
    tool: ToolName = "none"
    grounded: bool = False            # True only if a tool result supports the text
    outcome: Outcome = "answered"
    lang: Optional[Lang] = None


class Metadata(BaseModel):
    """What survives a conversation. MUST contain no free text, numbers, or names."""
    topic: str
    subtopic: Optional[str] = None
    caza: Optional[str] = None
    lang: Optional[Lang] = None
    outcome: Outcome = "answered"
    day: str                          # ISO date, day only (no time)


# ---- Interfaces (owners implement these) -----------------------------------
class LLMClient(Protocol):            # owner: A
    def generate(self, system: str, prompt: str, context: str = "") -> str: ...
    def classify(self, text: str, labels: list[str]) -> str: ...
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Transcriber(Protocol):          # owner: B  (voice notes)
    def transcribe(self, audio: bytes, mime: str) -> tuple[str, Optional[Lang]]: ...


class ProcedureSearch(Protocol):      # owner: B
    def search(self, query: str, lang: Optional[Lang] = None, k: int = 4) -> list[Doc]: ...


class DirectorySearch(Protocol):      # owner: D
    def nearest(self, kind: str, caza: Optional[str] = None,
                lat: Optional[float] = None, lon: Optional[float] = None,
                k: int = 3) -> list[Facility]: ...


class MedicineLookup(Protocol):       # owner: D
    def find(self, name: str) -> list[DrugRecord]: ...


# redact(text) -> text               # owner: B  (ai/redaction.py)
# classify(transcript) -> Metadata   # owner: B  (ai/classifier.py)

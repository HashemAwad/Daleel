"""FastAPI app — the single backend both channels call. Owner: A.
Run:  PYTHONPATH=src uvicorn core.app:app --reload
"""
from __future__ import annotations
import uuid
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from shared.contracts import Inquiry, Answer
from core import pipeline

WEB_DIR = Path(__file__).resolve().parents[2] / "web"

app = FastAPI(title="Daleel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/")
def widget() -> FileResponse:
    """Serve the chat widget same-origin so /chat works with no CORS fuss."""
    return FileResponse(WEB_DIR / "index.html")


class ChatIn(BaseModel):
    channel: str = "web"
    text: str = ""
    user_ref: str = "anon"
    lang: str | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True, "service": "daleel"}


@app.post("/chat", response_model=Answer)
def chat(body: ChatIn) -> Answer:
    inq = Inquiry(
        id=str(uuid.uuid4()), channel=body.channel, text=body.text,
        lang=body.lang, user_ref=body.user_ref,
    )
    return pipeline.handle(inq)


# Mount C's channel routes (WhatsApp webhook, /dashboard, /join, metrics).
# Guarded: a channels import/config error must never take the core app down.
try:
    from channels import register
    register(app)
except Exception as _e:  # pragma: no cover
    import logging
    logging.getLogger(__name__).warning("channels not mounted: %s", type(_e).__name__)

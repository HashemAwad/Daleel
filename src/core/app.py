"""FastAPI app — the single backend both channels call. Owner: A.
Run:  PYTHONPATH=src uvicorn core.app:app --reload
"""
from __future__ import annotations
import uuid
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from shared.contracts import Inquiry, Answer
from core import pipeline

app = FastAPI(title="Daleel")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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

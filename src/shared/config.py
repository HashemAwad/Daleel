"""Central config, read from env. Import `settings` anywhere."""
from __future__ import annotations
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("DALEEL_MODEL", "claude-sonnet-4-6")
    model_provider = os.getenv("DALEEL_MODEL_PROVIDER", "anthropic")  # anthropic | selfhost
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    database_url = os.getenv("DATABASE_URL", "postgresql://daleel:daleel@localhost:5432/daleel")
    twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "")
    public_base_url = os.getenv("PUBLIC_BASE_URL", "")
    retention_idle_minutes = int(os.getenv("RETENTION_IDLE_MINUTES", "30"))
    session_hash_salt = os.getenv("SESSION_HASH_SALT", "change-me")
    stt_provider = os.getenv("STT_PROVIDER", "whisper")
    stt_api_key = os.getenv("STT_API_KEY", "")


settings = Settings()

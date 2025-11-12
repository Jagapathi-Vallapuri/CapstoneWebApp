from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import Field
import os
import json



class Settings(BaseSettings):
    SECRET_KEY: Optional[str] = None
    DATABASE_URL: Optional[str] = None

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # S3 / file storage
    S3_BUCKET: str = ""
    S3_REGION: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""

    # LLM / Chat settings
    LLM_PROVIDER: str = "gemini"
    LLM_API_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_MAX_TOKENS: int = 2048
    LLM_TEMPERATURE: float = 0.2
    LLM_SYSTEM_PROMPT: Optional[str] = None

    # Detection service URL
    detection_url: Optional[str] = None 

    ALLOWED_ORIGINS: List[str] = Field(default_factory=list)

    class Config:
        env_file = ".env"


settings = Settings()

raw_allowed = os.getenv("ALLOWED_ORIGINS")
if raw_allowed:
    try:
        parsed = json.loads(raw_allowed)
        if isinstance(parsed, list):
            settings.ALLOWED_ORIGINS = parsed
    except Exception:
        settings.ALLOWED_ORIGINS = [s.strip() for s in raw_allowed.split(',') if s.strip()]

if not settings.SECRET_KEY or not settings.DATABASE_URL:
    raise RuntimeError("Environment variables SECRET_KEY and DATABASE_URL must be set (see backend/.env.example)")

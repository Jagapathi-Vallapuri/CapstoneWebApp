from pydantic_settings import BaseSettings
from typing import List, Optional
from pydantic import Field


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

    # CORS origins
    ALLOWED_ORIGINS: List[str] = Field(default_factory=list)

    class Config:
        env_file = ".env"


settings = Settings()

if not settings.SECRET_KEY or not settings.DATABASE_URL:
    raise RuntimeError("Environment variables SECRET_KEY and DATABASE_URL must be set (see backend/.env.example)")

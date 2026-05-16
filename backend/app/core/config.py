"""
Application configuration — all settings loaded from environment variables.
Never hardcode secrets. Use .env locally, set env vars in production.
"""
import ast
import json
from functools import lru_cache
from typing import Any, List

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = "DocuMind"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # ─── Security ───────────────────────────────────────────────────────────
    SECRET_KEY: str                          # Generate: openssl rand -hex 32
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Render env vars might be parsed as strings by pydantic_settings JSON decode
    # if we use `List[str]`, so we tell pydantic_settings not to automatically parse
    # it as JSON by making the type hint `str | List[str]` initially, then forcing it.
    ALLOWED_ORIGINS: Any = ["http://localhost:5173", "https://documind.vercel.app"]

    @field_validator("ALLOWED_ORIGINS", "ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def parse_list_vars(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            # Try to parse as JSON first (e.g. '["a", "b"]')
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    try:
                        return ast.literal_eval(v)
                    except Exception:
                        pass
            # Fallback to comma-separated string (e.g. 'a, b, c')
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # ─── Database (Supabase / PostgreSQL) ───────────────────────────────────
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_KEY: str              # Server-side admin key
    DATABASE_URL: str                      # postgresql+asyncpg://user:pass@host/db

    # ─── Storage ────────────────────────────────────────────────────────────
    SUPABASE_BUCKET: str = "documents"
    MAX_FILE_SIZE_MB: int = 20
    ALLOWED_EXTENSIONS: Any = ["pdf", "txt", "docx", "md"]

    # ─── AI / LLM — Google Gemini (free tier) ───────────────────────────────
    GOOGLE_API_KEY: str
    GEMINI_CHAT_MODEL: str = "gemini-1.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "text-embedding-004"

    # ─── RAG / Chunking ─────────────────────────────────────────────────────
    CHUNK_SIZE: int = 800                 # tokens per chunk
    CHUNK_OVERLAP: int = 100             # overlap between consecutive chunks
    MAX_CHUNKS_PER_DOC: int = 200        # hard cap to control cost
    RAG_TOP_K: int = 6                   # chunks to retrieve per query
    RAG_SIMILARITY_THRESHOLD: float = 0.70

    # ─── Rate limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60        # requests per window
    RATE_LIMIT_WINDOW: int = 60          # window in seconds
    AI_RATE_LIMIT_REQUESTS: int = 10     # AI calls per window (cost control)
    AI_RATE_LIMIT_WINDOW: int = 60

    # ─── Redis (caching) ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 3600        # 1 hour default TTL

    # ─── Quotas (no billing) ────────────────────────────────────────────────
    # Maximum number of documents a single account can process. Set to 0 to disable.
    FREE_DOC_LIMIT: int = 10

    # ─── Monitoring ─────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — loaded once at startup."""
    return Settings()

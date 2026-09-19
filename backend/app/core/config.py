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

    # ─── Multi-Provider AI / LLM (LiteLLM abstraction) ──────────────────────
    LLM_PROVIDER: str = "gemini"         # gemini | openai | anthropic | groq | ollama
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    OLLAMA_API_BASE: str = "http://localhost:11434"

    # Default to current generation free-tier models verified via verify_gemini_key.py
    LLM_MODEL: str = "gemini/gemini-3.6-flash"
    EMBEDDING_MODEL: str = "gemini/gemini-embedding-001"
    EMBEDDING_DIM: int = 768
    LLM_MAX_CONCURRENCY: int = 3

    # Backward compatibility properties
    GEMINI_CHAT_MODEL: str = "gemini-3.6-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # ─── RAG / Retrieval & Re-ranking ───────────────────────────────────────
    CHUNK_SIZE: int = 800                 # tokens per chunk
    CHUNK_OVERLAP: int = 100             # overlap between consecutive chunks
    MAX_CHUNKS_PER_DOC: int = 200        # hard cap to control cost
    RAG_TOP_K: int = 6                   # final chunks for LLM context
    RAG_INITIAL_TOP_K: int = 15          # candidate pool for 2-stage reranking
    RAG_SIMILARITY_THRESHOLD: float = 0.50
    ENABLE_RERANKING: bool = True
    ENABLE_HYBRID_SEARCH: bool = True

    # ─── Rate limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_REQUESTS: int = 60        # requests per window
    RATE_LIMIT_WINDOW: int = 60          # window in seconds
    AI_RATE_LIMIT_REQUESTS: int = 10     # AI calls per window (cost control)
    AI_RATE_LIMIT_WINDOW: int = 60

    # ─── Redis (caching) ────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 3600        # 1 hour default TTL

    # ─── Stripe (billing) ───────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_PRO: str = ""       # Monthly Pro plan price ID
    STRIPE_FREE_DOC_LIMIT: int = 3
    STRIPE_FREE_QUERY_LIMIT: int = 20   # Per day
    FRONTEND_URL: str = "http://localhost:5173"

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

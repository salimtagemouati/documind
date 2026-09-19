"""
Pydantic schemas — strict input validation and clean API response shapes.
Never expose internal model fields (hashed_password, storage_path, etc.) to the client.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth ────────────────────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=200)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


# ─── User ────────────────────────────────────────────────────────────────────
class UserPublic(BaseModel):
    id: UUID
    email: EmailStr
    full_name: Optional[str]
    role: str
    is_verified: bool
    documents_processed: int
    queries_made: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Document ────────────────────────────────────────────────────────────────
class DocumentUploadResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    created_at: datetime


class DocumentMeta(BaseModel):
    id: UUID
    filename: str
    file_type: str
    file_size_bytes: int
    status: str
    chunk_count: int
    token_count: int
    page_count: Optional[int]
    language: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class EntityExtractionResult(BaseModel):
    persons: List[str] = []
    organizations: List[str] = []
    locations: List[str] = []
    dates: List[str] = []
    technologies: List[str] = []
    monetary_values: List[str] = []
    other: List[str] = []


class SentimentResult(BaseModel):
    label: str                     # Positive | Negative | Neutral | Mixed
    score: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    tone: str
    explanation: str


class DocumentAnalysis(BaseModel):
    id: UUID
    filename: str
    status: str
    summary: Optional[str]
    entities: Optional[EntityExtractionResult]
    keywords: Optional[List[str]]
    sentiment: Optional[SentimentResult]
    chunk_count: int
    token_count: int
    page_count: Optional[int]
    language: Optional[str]
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ─── RAG / Q&A ───────────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=1000)
    document_id: UUID
    max_tokens: int = Field(default=800, ge=100, le=2000)


class SourceChunk(BaseModel):
    content: str
    chunk_index: int
    page_number: Optional[int]
    similarity_score: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceChunk]
    model_used: str
    tokens_used: int
    latency_ms: int
    from_cache: bool
    query_id: UUID
    reranked: bool = False


# ─── Multi-Document RAG ──────────────────────────────────────────────────────
class MultiQueryRequest(BaseModel):
    document_ids: List[UUID] = Field(min_length=2, max_length=5)
    question: str = Field(min_length=1, max_length=2000)
    max_tokens: int = Field(default=1000, ge=100, le=4000)
    enable_rerank: bool = Field(default=True)


class MultiSourceChunk(BaseModel):
    content: str
    chunk_index: int
    document_id: UUID
    document_name: str
    page_number: Optional[int] = None
    similarity_score: float
    rerank_score: Optional[float] = None
    # Aliases/convenience fields
    document_title: Optional[str] = None
    snippet: Optional[str] = None
    page: Optional[int] = None
    score: Optional[float] = None

    def model_post_init(self, __context):
        if self.document_title is None:
            self.document_title = self.document_name
        if self.snippet is None:
            self.snippet = self.content
        if self.page is None:
            self.page = self.page_number
        if self.score is None:
            self.score = self.rerank_score if self.rerank_score is not None else self.similarity_score


class MultiQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[MultiSourceChunk]
    documents_queried: List[dict]
    model_used: str
    tokens_used: int
    latency_ms: int
    reranked: bool = False
    from_cache: bool = False
    query_id: UUID


# ─── Evaluation / Benchmark ──────────────────────────────────────────────────
class BenchmarkMetric(BaseModel):
    name: str
    baseline: float
    reranked: float
    delta: float
    description: str


class BenchmarkSummary(BaseModel):
    timestamp: str
    evaluated_models: dict
    total_cases: int
    metrics: List[BenchmarkMetric]
    category_breakdown: Optional[dict] = None
    details: List[dict]


# ─── Query history ───────────────────────────────────────────────────────────
class QueryHistoryItem(BaseModel):
    id: UUID
    question: str
    answer: str
    tokens_used: int
    latency_ms: Optional[int]
    from_cache: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Analytics ───────────────────────────────────────────────────────────────
class UserStats(BaseModel):
    documents_uploaded: int
    queries_made: int
    ai_tokens_used: int
    avg_query_latency_ms: Optional[float]
    cache_hit_rate: Optional[float]


class AdminStats(BaseModel):
    total_users: int
    total_documents: int
    total_queries: int
    total_tokens_used: int
    documents_today: int
    queries_today: int


# ─── Common ──────────────────────────────────────────────────────────────────
class MessageResponse(BaseModel):
    message: str
    detail: Optional[Any] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int

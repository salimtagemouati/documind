"""
SQLAlchemy ORM models for async PostgreSQL (via asyncpg).
These mirror the Supabase table definitions — keep them in sync.
"""
import enum
import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def utcnow():
    return datetime.now(timezone.utc)


# ─── Enums ───────────────────────────────────────────────────────────────────
class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    premium = "premium"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


# ─── Users ───────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    role = Column(SAEnum(UserRole), default=UserRole.user, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)

    # Usage tracking
    documents_processed = Column(Integer, default=0)
    queries_made = Column(Integer, default=0)
    ai_tokens_used = Column(Integer, default=0)

    # Billing (Stripe)
    stripe_customer_id = Column(String(255), unique=True, nullable=True)
    subscription_status = Column(String(50), default="inactive")   # active | inactive | trialing | canceled | past_due
    subscription_tier = Column(String(50), default="free")          # free | pro
    stripe_subscription_id = Column(String(255), nullable=True)
    daily_queries_count = Column(Integer, default=0)
    daily_queries_date = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    queries = relationship("QueryHistory", back_populates="user", cascade="all, delete-orphan")


# ─── Documents ───────────────────────────────────────────────────────────────
class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    # File metadata
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)          # pdf, txt, docx
    file_size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String(1000), nullable=False)     # Supabase storage path
    storage_url = Column(String(2000))                      # Public URL if applicable

    # Processing status
    status = Column(SAEnum(DocumentStatus), default=DocumentStatus.pending, nullable=False)
    error_message = Column(Text)

    # Extracted content
    raw_text = Column(Text)
    chunk_count = Column(Integer, default=0)
    token_count = Column(Integer, default=0)
    page_count = Column(Integer)

    # AI analysis results (cached)
    summary = Column(Text)
    entities = Column(JSON)                                  # {persons:[], orgs:[], dates:[], ...}
    keywords = Column(ARRAY(String))
    sentiment = Column(JSON)                                 # {label, score, confidence}
    language = Column(String(10))

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    processed_at = Column(DateTime(timezone=True))

    # Relationships
    owner = relationship("User", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    queries = relationship("QueryHistory", back_populates="document")


# ─── Document Chunks (for RAG) ───────────────────────────────────────────────
class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    chunk_index = Column(Integer, nullable=False)           # Position in document
    content = Column(Text, nullable=False)                  # Raw chunk text
    token_count = Column(Integer, nullable=False)
    page_number = Column(Integer)                           # For PDFs

    # Durable vector embedding in pgvector (PostgreSQL)
    embedding = Column(Vector(768), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    document = relationship("Document", back_populates="chunks")


# ─── Query History ───────────────────────────────────────────────────────────
class QueryHistory(Base):
    __tablename__ = "query_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    document_ids = Column(JSON, nullable=True)             # List of document IDs for multi-doc synthesis queries

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sources = Column(JSON)                                  # List of chunk excerpts used
    model_used = Column(String(100))
    tokens_used = Column(Integer, default=0)
    latency_ms = Column(Integer)                            # Response time tracking
    from_cache = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    user = relationship("User", back_populates="queries")
    document = relationship("Document", back_populates="queries")


# ─── Analytics (aggregated counters) ─────────────────────────────────────────
class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime(timezone=True), nullable=False, unique=True, index=True)
    documents_uploaded = Column(Integer, default=0)
    queries_processed = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)
    unique_users = Column(Integer, default=0)
    cache_hit_rate = Column(Float, default=0.0)
    avg_query_latency_ms = Column(Float, default=0.0)

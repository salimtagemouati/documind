-- ============================================================
-- DocuMind Database Schema
-- Run this in Supabase SQL Editor (or psql directly)
-- ============================================================

-- Enable UUID, pg_trgm, and pgvector extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- for text search
CREATE EXTENSION IF NOT EXISTS "vector";   -- for durable pgvector storage

-- ─── ENUMS ─────────────────────────────────────────────────
CREATE TYPE user_role AS ENUM ('user', 'premium', 'admin');
CREATE TYPE doc_status AS ENUM ('pending', 'processing', 'ready', 'failed');

-- ─── USERS ─────────────────────────────────────────────────
CREATE TABLE users (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email                TEXT UNIQUE NOT NULL,
    hashed_password      TEXT NOT NULL,
    full_name            TEXT,
    role                 user_role NOT NULL DEFAULT 'user',
    is_active            BOOLEAN NOT NULL DEFAULT TRUE,
    is_verified          BOOLEAN NOT NULL DEFAULT FALSE,
    documents_processed  INTEGER NOT NULL DEFAULT 0,
    queries_made         INTEGER NOT NULL DEFAULT 0,
    ai_tokens_used       INTEGER NOT NULL DEFAULT 0,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users (email);

-- Auto-update updated_at on any row change
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── DOCUMENTS ─────────────────────────────────────────────
CREATE TABLE documents (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            TEXT NOT NULL,
    original_filename   TEXT NOT NULL,
    file_type           TEXT NOT NULL,
    file_size_bytes     INTEGER NOT NULL,
    storage_path        TEXT NOT NULL,
    storage_url         TEXT,
    status              doc_status NOT NULL DEFAULT 'pending',
    error_message       TEXT,
    raw_text            TEXT,
    chunk_count         INTEGER NOT NULL DEFAULT 0,
    token_count         INTEGER NOT NULL DEFAULT 0,
    page_count          INTEGER,
    summary             TEXT,
    entities            JSONB,
    keywords            TEXT[],
    sentiment           JSONB,
    language            VARCHAR(10),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ
);

CREATE INDEX idx_documents_user_id ON documents (user_id);
CREATE INDEX idx_documents_status ON documents (status);
CREATE INDEX idx_documents_created_at ON documents (created_at DESC);

-- Full-text search on document filename and summary
CREATE INDEX idx_documents_fts ON documents
    USING GIN (to_tsvector('english', coalesce(original_filename, '') || ' ' || coalesce(summary, '')));

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ─── DOCUMENT CHUNKS (with pgvector) ───────────────────────
CREATE TABLE document_chunks (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id    UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index    INTEGER NOT NULL,
    content        TEXT NOT NULL,
    token_count    INTEGER NOT NULL,
    page_number    INTEGER,
    embedding      vector(768),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (document_id, chunk_index)
);

CREATE INDEX idx_chunks_document_id ON document_chunks (document_id);
CREATE INDEX idx_chunks_embedding_hnsw ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_content_fts ON document_chunks USING GIN (to_tsvector('english', content));

-- ─── QUERY HISTORY ─────────────────────────────────────────
CREATE TABLE query_history (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id   UUID REFERENCES documents(id) ON DELETE SET NULL,
    document_ids  JSONB,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    sources       JSONB,
    model_used    TEXT,
    tokens_used   INTEGER NOT NULL DEFAULT 0,
    latency_ms    INTEGER,
    from_cache    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_query_history_user_id ON query_history (user_id);
CREATE INDEX idx_query_history_document_id ON query_history (document_id);
CREATE INDEX idx_query_history_created_at ON query_history (created_at DESC);

-- ─── DAILY STATS (analytics) ───────────────────────────────
CREATE TABLE daily_stats (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date                    DATE UNIQUE NOT NULL,
    documents_uploaded      INTEGER NOT NULL DEFAULT 0,
    queries_processed       INTEGER NOT NULL DEFAULT 0,
    total_tokens_used       INTEGER NOT NULL DEFAULT 0,
    unique_users            INTEGER NOT NULL DEFAULT 0,
    cache_hit_rate          FLOAT NOT NULL DEFAULT 0,
    avg_query_latency_ms    FLOAT NOT NULL DEFAULT 0,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_daily_stats_date ON daily_stats (date DESC);

-- ─── ROW LEVEL SECURITY ────────────────────────────────────
-- Users can only see and modify their own data

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_history ENABLE ROW LEVEL SECURITY;

-- Users table: users see only their own row
CREATE POLICY "users_select_own" ON users FOR SELECT USING (id = auth.uid()::UUID);
CREATE POLICY "users_update_own" ON users FOR UPDATE USING (id = auth.uid()::UUID);

-- Documents: full CRUD for owner
CREATE POLICY "docs_select_own" ON documents FOR SELECT USING (user_id = auth.uid()::UUID);
CREATE POLICY "docs_insert_own" ON documents FOR INSERT WITH CHECK (user_id = auth.uid()::UUID);
CREATE POLICY "docs_update_own" ON documents FOR UPDATE USING (user_id = auth.uid()::UUID);
CREATE POLICY "docs_delete_own" ON documents FOR DELETE USING (user_id = auth.uid()::UUID);

-- Chunks: read-only for document owner
CREATE POLICY "chunks_select_own" ON document_chunks FOR SELECT
    USING (document_id IN (SELECT id FROM documents WHERE user_id = auth.uid()::UUID));

-- Query history: user owns their queries
CREATE POLICY "qh_select_own" ON query_history FOR SELECT USING (user_id = auth.uid()::UUID);
CREATE POLICY "qh_insert_own" ON query_history FOR INSERT WITH CHECK (user_id = auth.uid()::UUID);

-- ─── SUPABASE STORAGE ──────────────────────────────────────
-- Run this in the Supabase Storage section or via API:
-- 1. Create bucket named "documents" (private)
-- 2. Policy: authenticated users can upload/read only their own files
--    Path pattern: {user_id}/*

-- ─── SEED: default admin user ──────────────────────────────
-- Replace password hash with: python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('AdminPass123'))"
-- INSERT INTO users (email, hashed_password, full_name, role, is_verified)
-- VALUES ('admin@documind.app', '<bcrypt_hash>', 'DocuMind Admin', 'admin', TRUE);

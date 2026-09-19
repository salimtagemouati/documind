-- ============================================================
-- DocuMind Migration 003: pgvector & Hybrid Search
-- Replaces FAISS with in-database vector storage
-- ============================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add embedding column to document_chunks
-- Default dimension 768 matches Gemini text-embedding-004 / gemini-embedding-001
ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding vector(768);

-- 3. HNSW index for high-performance approximate nearest neighbor search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
ON document_chunks 
USING hnsw (embedding vector_cosine_ops);

-- 4. Full-Text Search GIN index on chunk content for Hybrid Search
CREATE INDEX IF NOT EXISTS idx_chunks_content_fts 
ON document_chunks 
USING GIN (to_tsvector('english', content));

-- 5. Support multi-document query tracking in query_history
ALTER TABLE query_history ADD COLUMN IF NOT EXISTS document_ids JSONB;

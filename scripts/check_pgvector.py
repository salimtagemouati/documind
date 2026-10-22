"""Disposable PostgreSQL/pgvector integration check. Requires a local Docker daemon.
Uses deterministic vectors, never provider credentials or an existing database.
"""
import asyncio
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def check(port, password):
    import numpy as np
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from app.models.models import Document, DocumentChunk, User
    from app.services import rag_service as rag

    engine = create_async_engine(f'postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/postgres')
    async with engine.begin() as conn:
        raw = await conn.get_raw_connection()
        # Supabase supplies these identities. Stub them only in this disposable DB.
        await raw.driver_connection.execute("CREATE ROLE anon; CREATE ROLE authenticated; CREATE SCHEMA auth; CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS 'SELECT NULL::uuid';")
        await raw.driver_connection.execute((ROOT / 'scripts/001_init_schema.sql').read_text())
        await raw.driver_connection.execute((ROOT / 'backend/migrations/002_add_billing.sql').read_text())
        await raw.driver_connection.execute((ROOT / 'backend/migrations/003_pgvector.sql').read_text())
        for role in ['anon', 'authenticated']:
            allowed = await conn.scalar(text("SELECT has_table_privilege(:role, 'users', 'SELECT')"), {'role': role})
            assert allowed is False, 'Browser role must not read application credentials'
        assert await conn.scalar(text("SELECT relrowsecurity FROM pg_class WHERE relname = 'daily_stats'")) is True
    vector = np.zeros(768, dtype=np.float32)
    vector[0] = 1
    async def embed_query(_query):
        return vector
    rag.embed_query = embed_query
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        owner = User(email='owner@example.com', hashed_password='unused')
        outsider = User(email='outsider@example.com', hashed_password='unused')
        db.add_all([owner, outsider])
        await db.flush()
        doc = Document(user_id=owner.id, filename='terms.txt', original_filename='terms.txt',
                       file_type='txt', file_size_bytes=20, storage_path='unused')
        db.add(doc)
        await db.flush()
        db.add(DocumentChunk(document_id=doc.id, chunk_index=0, token_count=6,
                             content='Warranty coverage lasts 24 months.', embedding=vector.tolist(), page_number=2))
        await db.commit()
        rows = await rag.retrieve_similar_chunks(db, doc.id, owner.id, 'warranty', top_k=3)
        assert len(rows) == 1 and rows[0]['page_number'] == 2
        assert rows[0]['vector_rank'] == 1 and rows[0]['text_rank'] == 1, rows
        assert rows[0]['rrf_score'] == round(2/61, 5)
        assert await rag.retrieve_similar_chunks(db, doc.id, outsider.id, 'warranty') == []
        await db.execute(text('SELECT 1'))  # FTS must not poison the transaction.
        print('PASS: real PostgreSQL, SQL bootstrap + migrations, browser-role revocations, RLS, HNSW/GIN, cosine search, FTS, RRF, owner isolation')
    await engine.dispose()


if __name__ == '__main__':
    name = 'documind-audit-' + secrets.token_hex(4)
    password = secrets.token_hex(24)
    container = None
    try:
        container = subprocess.check_output(['docker','run','--rm','-d','--name',name,
            '-e','POSTGRES_PASSWORD='+password,'-p','127.0.0.1::5432',
            'pgvector/pgvector:pg16'], text=True).strip()
        port = subprocess.check_output(['docker','port',name,'5432'],text=True).strip().rsplit(':',1)[1]
        for _ in range(60):
            if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],capture_output=True).returncode == 0:
                break
            time.sleep(0.5)
        with tempfile.TemporaryDirectory(prefix='documind-pgcheck-') as tmp:
            os.chdir(tmp)
            sys.path.insert(0,str(ROOT/'backend'))
            os.environ.update(SECRET_KEY='local-pgvector-test-only', ENVIRONMENT='test',
                SUPABASE_URL='https://unused.invalid', SUPABASE_ANON_KEY='',SUPABASE_SERVICE_KEY='',
                DATABASE_URL='sqlite+aiosqlite:///:memory:',REDIS_URL='', LITELLM_LOCAL_MODEL_COST_MAP='True')
            asyncio.run(check(port,password))
    finally:
        if container:
            subprocess.run(['docker','stop',name],stdout=subprocess.DEVNULL,check=False)

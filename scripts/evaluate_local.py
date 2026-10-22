"""Compare frozen/current chunking through real SQLite retrieval, without providers.

Run: backend/.venv/bin/python scripts/evaluate_local.py
Never reads developer credentials or writes to an existing database.
"""
import asyncio
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


async def evaluate():
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.eval.baseline_chunker import chunk_text as baseline
    from app.models.models import Base, Document, DocumentStatus, User
    from app.services.document_processor import chunk_text
    from app.services.rag_service import build_document_index, retrieve_similar_chunks

    cases = json.loads((ROOT / 'backend/app/eval/local_cases.json').read_text())
    report = {'methodology': 'sqlite-source-provenance-v1', 'k': 3,
              'limitations': ['Synthetic fixtures; not representative of all documents',
                 'Real SQLite retrieval; no embeddings, PostgreSQL or LLM calls',
                 'Source-page accuracy is not semantic citation correctness',
                 'Answer quality and groundedness are unmeasured'], 'runs': {}}
    for label, chunker in [('baseline', baseline), ('current', chunk_text)]:
        engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            user = User(email='eval@example.com', hashed_password='unused')
            db.add(user)
            await db.flush()
            details = []
            for case in cases:
                doc = Document(user_id=user.id, filename=case['id']+'.pdf', original_filename=case['id']+'.pdf',
                    file_type='pdf', file_size_bytes=1, storage_path='unused', status=DocumentStatus.ready)
                db.add(doc)
                await db.flush()
                # Baseline PDF extraction discarded blank pages and page separators.
                text = '\n\n'.join(p for p in case['pages'] if p) if label == 'baseline' else '\f'.join(case['pages'])
                chunks = chunker(text, chunk_size=60, chunk_overlap=10)
                await build_document_index(db, doc.id, chunks)
                start = time.perf_counter()
                found = await retrieve_similar_chunks(db, doc.id, user.id, case['question'], top_k=3)
                elapsed = (time.perf_counter() - start) * 1000
                hits = [c for c in found if case['expected_answer'].casefold() in c['content'].casefold()]
                details.append({'id': case['id'], 'retrieval_hit': bool(hits),
                    'correct_supporting_page': any(c['page_number'] == case['expected_page'] for c in hits),
                    'retrieval_latency_ms': round(elapsed, 3),
                    'retrieved_pages': [c['page_number'] for c in found]})
            report['runs'][label] = {'cases': len(details),
                'hit_rate_at_3': sum(c['retrieval_hit'] for c in details)/len(details),
                'supporting_page_accuracy_at_3': sum(c['correct_supporting_page'] for c in details)/len(details),
                'mean_retrieval_latency_ms': round(sum(c['retrieval_latency_ms'] for c in details)/len(details), 3),
                'details': details}
        await engine.dispose()
    output = ROOT / 'docs/local_retrieval_results.json'
    output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='documind-eval-') as tmp:
        os.chdir(tmp)
        sys.path.insert(0, str(ROOT / 'backend'))
        os.environ.update(SECRET_KEY='local-evaluation-only-not-a-deployment-secret',
            ENVIRONMENT='test', DATABASE_URL='sqlite+aiosqlite:///:memory:',
            SUPABASE_URL='https://unused.invalid', SUPABASE_ANON_KEY='', SUPABASE_SERVICE_KEY='',
            GOOGLE_API_KEY='', GEMINI_API_KEY='', OPENAI_API_KEY='', REDIS_URL='',
            LITELLM_LOCAL_MODEL_COST_MAP='True')
        asyncio.run(evaluate())

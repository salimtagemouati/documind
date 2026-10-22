from uuid import uuid4

import pytest

from app.models.models import Document, DocumentStatus, User
from app.services.model_options import sampling_options
from app.services.stripe_service import check_document_limit


@pytest.mark.asyncio
async def test_document_limit_counts_retained_files_not_lifetime_analyses(db_session, monkeypatch):
    from app.services import stripe_service
    monkeypatch.setattr(stripe_service.settings, 'STRIPE_FREE_DOC_LIMIT', 2)
    owner = User(id=uuid4(), email='slots@example.com', hashed_password='test', documents_processed=100)
    db_session.add(owner)
    await db_session.flush()
    await check_document_limit(str(owner.id), db_session)
    docs = [Document(id=uuid4(), user_id=owner.id, filename=f'{i}.txt', original_filename=f'{i}.txt',
                     file_type='txt', file_size_bytes=10, storage_path=f'test/{i}.txt', status=status)
            for i, status in enumerate([DocumentStatus.pending, DocumentStatus.failed])]
    db_session.add_all(docs)
    await db_session.flush()
    with pytest.raises(ValueError, match='Delete a document'):
        await check_document_limit(str(owner.id), db_session)
    await db_session.delete(docs[0])
    await db_session.flush()
    await check_document_limit(str(owner.id), db_session)
    assert owner.documents_processed == 100


@pytest.mark.parametrize('model', ['gemini/gemini-3.5-flash-lite', 'gemini/gemini-4-flash'])
def test_current_gemini_uses_default_sampling(model):
    assert sampling_options(model, 0.1) == {}


def test_older_and_other_models_keep_requested_sampling():
    assert sampling_options('gemini/gemini-2.5-flash', 0.1) == {'temperature': 0.1}
    assert sampling_options('gpt-4o-mini', 0.2) == {'temperature': 0.2}

"""Regression coverage for public-demo isolation and fresh-clone workflows."""
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_demo_password_cannot_create_unrestricted_session(async_client):
    await async_client.post('/api/v1/auth/demo')
    response = await async_client.post('/api/v1/auth/login', json={
        'email': 'demo@documind.app', 'password': 'DemoPassword123!',
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_demo_email_is_reserved_before_first_visit(async_client):
    response = await async_client.post('/api/v1/auth/register', json={
        'email': 'demo@documind.app', 'password': 'AttackPassword123!',
    })
    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize('path', ['/api/v1/documents/', '/api/v1/query/history'])
@pytest.mark.parametrize('params', [{'page_size': 0}, {'page': 0}, {'page_size': 101}])
async def test_invalid_pagination_returns_validation_error(async_client, path, params):
    auth = await async_client.post('/api/v1/auth/register', json={
        'email': 'pages@example.com', 'password': 'SecurePassword123!',
    })
    response = await async_client.get(path, params=params, headers={
        'Authorization': f"Bearer {auth.json()['access_token']}",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_sqlite_upload_process_delete_without_supabase(async_client, tmp_path, monkeypatch):
    from app.api.routes import documents

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(documents.settings, "LOCAL_UPLOAD_DIR", "data/uploads")
    auth = await async_client.post('/api/v1/auth/register', json={
        'email': 'local@example.com', 'password': 'SecurePassword123!',
    })
    headers = {'Authorization': f"Bearer {auth.json()['access_token']}"}
    with patch.object(documents.database, 'get_supabase_admin', side_effect=AssertionError('Local upload must not use Supabase')):
        uploaded = await async_client.post('/api/v1/documents/upload', headers=headers,
            files={'file': ('example.txt', b'The local service supports document analysis.', 'text/plain')})
        assert uploaded.status_code == 202
        doc_id = uploaded.json()['id']
        metadata = await async_client.get(f'/api/v1/documents/{doc_id}', headers=headers)
        assert metadata.json()['status'] == 'ready'
        analysis = await async_client.get(f'/api/v1/documents/{doc_id}/analysis', headers=headers)
        assert analysis.status_code == 200
        assert analysis.json()['summary']
        assert len(list((tmp_path / 'data' / 'uploads').rglob('*.txt'))) == 1
        removed = await async_client.delete(f'/api/v1/documents/{doc_id}', headers=headers)
        assert removed.status_code == 200
        assert not list((tmp_path / 'data' / 'uploads').rglob('*.txt'))


@pytest.mark.asyncio
async def test_legacy_demo_access_token_is_still_read_only(async_client):
    from app.core.security import create_access_token, decode_token

    demo = await async_client.post('/api/v1/auth/demo')
    user_id = decode_token(demo.json()['access_token'])['sub']
    legacy = create_access_token(user_id, extra={'role': 'premium'})
    response = await async_client.post('/api/v1/documents/upload',
        headers={'Authorization': f'Bearer {legacy}'},
        files={'file': ('attack.txt', b'An unrestricted demo upload.', 'text/plain')})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_deactivated_user_access_token_is_rejected(async_client, db_session):
    from sqlalchemy import select

    from app.models.models import User

    auth = await async_client.post('/api/v1/auth/register', json={
        'email': 'disabled@example.com', 'password': 'SecurePassword123!',
    })
    user = (await db_session.execute(select(User).where(User.email == 'disabled@example.com'))).scalar_one()
    user.is_active = False
    await db_session.commit()
    response = await async_client.get('/api/v1/documents/', headers={
        'Authorization': f"Bearer {auth.json()['access_token']}",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_provider_auth_failure_is_actionable_503(async_client, monkeypatch):
    import litellm

    from app.api.routes import query

    demo = await async_client.post('/api/v1/auth/demo')
    headers = {'Authorization': f"Bearer {demo.json()['access_token']}"}
    docs = (await async_client.get('/api/v1/documents/', headers=headers)).json()['items']

    async def rejected(**kwargs):
        raise litellm.AuthenticationError(message='secret provider details', model='test', llm_provider='gemini')

    monkeypatch.setattr(query, 'answer_question', rejected)
    response = await async_client.post('/api/v1/query/', headers=headers,
        json={'document_id': docs[0]['id'], 'question': 'What are the key points?'})
    assert response.status_code == 503
    assert 'configuration' in response.json()['detail']
    assert 'secret provider details' not in response.text


@pytest.mark.asyncio
async def test_failed_analysis_is_not_reported_ready(async_client, monkeypatch):
    from app.api.routes import documents

    async def rejected(*args, **kwargs):
        raise RuntimeError('private-provider-error')

    for name in ('summarize_document', 'extract_entities', 'analyze_sentiment', 'extract_keywords'):
        monkeypatch.setattr(documents, name, rejected)
    auth = await async_client.post('/api/v1/auth/register', json={
        'email': 'failure@example.com', 'password': 'SecurePassword123!',
    })
    headers = {'Authorization': f"Bearer {auth.json()['access_token']}"}
    uploaded = await async_client.post('/api/v1/documents/upload', headers=headers,
        files={'file': ('failure.txt', b'A document whose analysis provider is unavailable.', 'text/plain')})
    assert uploaded.status_code == 202
    metadata = await async_client.get(f"/api/v1/documents/{uploaded.json()['id']}", headers=headers)
    assert metadata.json()['status'] == 'failed'
    assert 'private-provider-error' not in metadata.text


def test_postgres_enum_names_match_sql_migrations():
    from app.models.models import Document, User

    assert User.__table__.c.role.type.name == 'user_role'
    assert Document.__table__.c.status.type.name == 'doc_status'

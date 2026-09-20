from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import JSON, inspect
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.db import database
from app.models.models import Document


def test_sqlite_keywords_use_json_binding():
    column_type = Document.__table__.c.keywords.type.dialect_impl(sqlite_dialect())
    assert isinstance(column_type, JSON)


def test_placeholder_database_host_has_actionable_error():
    validator = getattr(database, "validate_database_url", None)
    assert callable(validator), "database URL validation is missing"

    with pytest.raises(ValueError, match="DATABASE_URL is not configured.*docs/LOCAL_DEV.md"):
        validator("postgresql+asyncpg://user@your-project.example.invalid:5432/documind")


@pytest.mark.asyncio
async def test_sqlite_init_creates_application_tables(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'documind.db'}"
    test_engine = create_async_engine(url)
    try:
        connected = await database.init_db(db_engine=test_engine, database_url=url)
        async with test_engine.connect() as connection:
            table_names = await connection.run_sync(
                lambda sync_connection: inspect(sync_connection).get_table_names()
            )
    finally:
        await test_engine.dispose()

    assert connected is True
    assert {"users", "documents", "document_chunks", "query_history"}.issubset(table_names)


def test_app_starts_and_health_is_degraded_when_database_is_unreachable():
    with (
        patch.object(main, "init_db", AsyncMock(return_value=False)),
        patch.object(main, "retry_database_connection", AsyncMock(), create=True),
        patch.object(main, "check_database_health", AsyncMock(return_value=False), create=True),
        TestClient(main.app) as client,
    ):
        response = client.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "db": "unreachable"}


@pytest.mark.asyncio
async def test_database_dependency_returns_clean_503_when_unavailable():
    setter = getattr(database, "set_database_status", None)
    assert callable(setter), "database availability state is missing"
    setter(False, error_type="ConnectionError")

    dependency = database.get_db()
    with pytest.raises(HTTPException) as exc_info:
        await anext(dependency)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Database temporarily unavailable. Please retry shortly."


def test_retry_schedule_uses_bounded_backoff_then_thirty_seconds():
    schedule = getattr(database, "database_retry_delays", None)
    assert callable(schedule), "database retry schedule is missing"
    delays = schedule()

    assert [next(delays) for _ in range(7)] == [1, 2, 4, 8, 16, 30, 30]

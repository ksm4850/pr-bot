import asyncio
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from app.core.config import settings


@pytest_asyncio.fixture(scope="function")
async def test_db_path():
    """테스트용 임시 DB 경로 설정 + 테이블 생성"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    db_path = Path(db_path)

    original_path = settings.database_path
    settings.database_path = db_path

    from app.core.database import reset_engine, init_db

    reset_engine()
    await init_db()

    yield db_path

    settings.database_path = original_path
    reset_engine()

    if db_path.exists():
        db_path.unlink()


@pytest_asyncio.fixture
async def db_session(test_db_path):
    """Repository 테스트용 - ContextVar에 세션 설정"""
    from app.core import database

    async with database.AsyncSessionLocal() as session:
        token = database.db_session.set(session)
        yield session
        database.db_session.reset(token)
        await session.rollback()


@pytest_asyncio.fixture
async def client(test_db_path):
    """FastAPI TestClient (DB 초기화 포함, 미들웨어가 세션 관리)"""
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def sentry_payload() -> dict:
    """Sentry Issue Alert webhook payload (실제 구조)"""
    return {
        "action": "triggered",
        "installation": {"uuid": "7672a8c7-6744-4406-8495-69d6d74c0d9a"},
        "data": {
            "event": {
                "event_id": "3c71983fe8bc4b45ae3e59fd08bbb4e2",
                "issue_id": "7241469116",
                "title": "ZeroDivisionError: division by zero",
                "platform": "python",
                "level": "error",
                "culprit": "/api/test",
                "environment": "prod",
                "transaction": "/api/test",
                "web_url": "https://sentry.io/organizations/test/issues/7241469116/",
                "exception": {
                    "values": [
                        {
                            "type": "ZeroDivisionError",
                            "value": "division by zero",
                            "stacktrace": {
                                "frames": [
                                    {
                                        "filename": "starlette/routing.py",
                                        "abs_path": "/venv/lib/starlette/routing.py",
                                        "function": "app",
                                        "lineno": 100,
                                        "in_app": False,  # 라이브러리 코드
                                    },
                                    {
                                        "filename": "app/utils.py",
                                        "abs_path": "/app/app/utils.py",
                                        "function": "helper",
                                        "lineno": 50,
                                        "context_line": "    result = process(data)",
                                        "pre_context": ["def helper():", "    data = get_data()"],
                                        "post_context": ["    return result", ""],
                                        "in_app": True,  # 사용자 코드
                                    },
                                    {
                                        "filename": "app/main.py",
                                        "abs_path": "/app/app/main.py",
                                        "function": "trigger_error",
                                        "lineno": 42,
                                        "context_line": "    _ = 1 / 0",
                                        "pre_context": ["@app.get('/test')", "def trigger_error():"],
                                        "post_context": None,
                                        "in_app": True,  # 사용자 코드
                                    },
                                ]
                            },
                        }
                    ]
                },
            },
            "triggered_rule": "Error Monitor",
        },
        "actor": {"type": "application", "id": "sentry", "name": "Sentry"},
    }


@pytest.fixture
def sentry_payload_minimal() -> dict:
    """최소한의 Sentry payload (stacktrace 없음)"""
    return {
        "action": "triggered",
        "data": {
            "event": {
                "event_id": "abc123",
                "title": "Minimal error",
                "level": "warning",
            },
        },
    }

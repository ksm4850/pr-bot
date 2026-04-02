from contextlib import asynccontextmanager
from contextvars import ContextVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# 현재 요청의 DB 세션 (미들웨어가 설정, Repository가 사용)
db_session: ContextVar[AsyncSession] = ContextVar("db_session")


def get_database_url() -> str:
    """SQLite 비동기 URL 생성"""
    return f"sqlite+aiosqlite:///{settings.database_path}"


engine = create_async_engine(
    get_database_url(),
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """DB 초기화 (테이블 생성)"""
    from app.models.job import Base
    import app.models.project  # noqa: F401 - Base에 ProjectModel 등록

    # 디렉토리 생성
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def db_context():
    """Worker용 DB 세션 컨텍스트 매니저 (HTTP 미들웨어 없이 사용)"""
    async with AsyncSessionLocal() as session:
        token = db_session.set(session)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            db_session.reset(token)


def reset_engine():
    """엔진 재설정 (테스트용)"""
    global engine, AsyncSessionLocal
    engine = create_async_engine(get_database_url(), echo=False)
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

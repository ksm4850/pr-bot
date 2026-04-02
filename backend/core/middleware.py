from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core import database


class DBSessionMiddleware(BaseHTTPMiddleware):
    """요청마다 DB 세션 생성 → ContextVar 저장 → commit/rollback"""

    async def dispatch(self, request: Request, call_next):
        async with database.AsyncSessionLocal() as session:
            token = database.db_session.set(session)
            try:
                response = await call_next(request)
                if response.status_code < 400:
                    await session.commit()
                else:
                    await session.rollback()
                return response
            except Exception:
                await session.rollback()
                raise
            finally:
                database.db_session.reset(token)

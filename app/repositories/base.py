from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import db_session


class BaseRepository:
    @property
    def session(self) -> AsyncSession:
        return db_session.get()

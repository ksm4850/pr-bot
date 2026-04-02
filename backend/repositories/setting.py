from datetime import UTC, datetime

from sqlalchemy import select

from models.setting import SettingModel
from repositories.base import BaseRepository


class SettingRepository(BaseRepository):
    async def get(self, key: str) -> SettingModel | None:
        result = await self.session.execute(
            select(SettingModel).where(SettingModel.key == key)
        )
        return result.scalar_one_or_none()

    async def upsert(self, key: str, value: str) -> SettingModel:
        existing = await self.get(key)
        if existing:
            existing.value = value
            existing.updated_at = datetime.now(UTC)
            await self.session.flush()
            return existing

        db_setting = SettingModel(
            key=key,
            value=value,
            updated_at=datetime.now(UTC),
        )
        self.session.add(db_setting)
        await self.session.flush()
        return db_setting

    async def list_all(self) -> list[SettingModel]:
        result = await self.session.execute(
            select(SettingModel).order_by(SettingModel.key)
        )
        return list(result.scalars().all())

    async def delete(self, key: str) -> bool:
        db_setting = await self.get(key)
        if not db_setting:
            return False
        await self.session.delete(db_setting)
        await self.session.flush()
        return True
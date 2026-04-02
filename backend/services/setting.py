from models.setting import Setting
from repositories.setting import SettingRepository

# 설정 키 상수
DOORAY_WEBHOOK_URL = "dooray_webhook_url"
NOTIFICATION_ENABLED = "notification_enabled"


class SettingService:
    def __init__(self, repo: SettingRepository | None = None):
        self.repo = repo or SettingRepository()

    async def get(self, key: str) -> Setting | None:
        db_setting = await self.repo.get(key)
        return Setting.from_orm(db_setting) if db_setting else None

    async def upsert(self, key: str, value: str) -> Setting:
        db_setting = await self.repo.upsert(key, value)
        return Setting.from_orm(db_setting)

    async def get_all(self) -> dict[str, str]:
        db_settings = await self.repo.list_all()
        return {s.key: s.value for s in db_settings}

    async def delete(self, key: str) -> bool:
        return await self.repo.delete(key)

    async def can_notify(self) -> tuple[bool, str | None]:
        """알림 발송 가능 여부 + webhook URL 반환.

        Returns:
            (True, url) — 발송 가능
            (False, None) — 설정 꺼짐 또는 URL 미설정
        """
        all_settings = await self.get_all()
        enabled = all_settings.get(NOTIFICATION_ENABLED, "false") == "true"
        url = all_settings.get(DOORAY_WEBHOOK_URL)
        if enabled and url:
            return True, url
        return False, None
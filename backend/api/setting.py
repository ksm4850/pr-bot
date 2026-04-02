from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.notifications import DoorayNotificationSender, NotificationMessage
from services.setting import DOORAY_WEBHOOK_URL, NOTIFICATION_ENABLED, SettingService

router = APIRouter()
service = SettingService()


class SettingsResponse(BaseModel):
    dooray_webhook_url: str | None = None
    notification_enabled: bool = False


class UpdateSettingsRequest(BaseModel):
    dooray_webhook_url: str | None = None
    notification_enabled: bool | None = None


@router.get("", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    """전체 설정 조회"""
    all_settings = await service.get_all()
    return SettingsResponse(
        dooray_webhook_url=all_settings.get(DOORAY_WEBHOOK_URL),
        notification_enabled=all_settings.get(NOTIFICATION_ENABLED, "false") == "true",
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(body: UpdateSettingsRequest) -> SettingsResponse:
    """설정 업데이트"""
    if body.dooray_webhook_url is not None:
        if body.dooray_webhook_url == "":
            await service.delete(DOORAY_WEBHOOK_URL)
        else:
            await service.upsert(DOORAY_WEBHOOK_URL, body.dooray_webhook_url)

    if body.notification_enabled is not None:
        await service.upsert(NOTIFICATION_ENABLED, str(body.notification_enabled).lower())

    return await get_settings()


class TestNotificationRequest(BaseModel):
    webhook_url: str


@router.post("/test-notification")
async def test_notification(body: TestNotificationRequest):
    """테스트 알림 발송 (저장 없이 입력된 URL로 직접 발송)"""
    sender = DoorayNotificationSender(body.webhook_url)
    message = NotificationMessage(
        bot_name="PR-Bot",
        text="테스트 알림",
        title="PR-Bot 테스트 알림",
        attachment_text="알림이 정상적으로 수신되었습니다.",
        color="blue",
    )
    ok = await sender.send(message)
    if not ok:
        raise HTTPException(status_code=502, detail="알림 발송에 실패했습니다. URL을 확인해주세요.")
    return {"ok": True}
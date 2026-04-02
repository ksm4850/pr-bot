import logging

import httpx

from app.services.notifications.base import NotificationMessage, NotificationSender

logger = logging.getLogger(__name__)


class DoorayNotificationSender(NotificationSender):
    """Dooray 웹훅 알림 발송"""

    def __init__(self, webhook_url: str, bot_name: str = "PR-Bot", bot_icon_url: str | None = None):
        self.webhook_url = webhook_url
        self.bot_name = bot_name
        self.bot_icon_url = bot_icon_url

    @property
    def name(self) -> str:
        return "dooray"

    async def send(self, message: NotificationMessage) -> bool:
        payload = {
            "botName": self.bot_name,
            "text": message.title,
            "attachments": [
                {
                    "title": message.title,
                    "text": message.text,
                    "color": message.color,
                }
            ],
        }

        if self.bot_icon_url:
            payload["botIconImage"] = self.bot_icon_url

        if message.title_link:
            payload["attachments"][0]["titleLink"] = message.title_link

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
                return True
        except httpx.HTTPError:
            logger.exception("Dooray 알림 발송 실패")
            return False

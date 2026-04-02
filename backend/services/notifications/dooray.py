import logging

import httpx

from services.notifications.base import NotificationMessage, NotificationSender

logger = logging.getLogger(__name__)


class DoorayNotificationSender(NotificationSender):
    """Dooray 웹훅 알림 발송"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "dooray"

    async def send(self, message: NotificationMessage) -> bool:
        payload = {
            "botName": message.bot_name,
            "botIconImage": message.bot_icon_image,
            "text": message.text,
            "attachments": [
                {
                    "title": message.title,
                    "titleLink": message.title_link,
                    "text": message.attachment_text,
                    "color": message.color,
                }
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
                return True
        except httpx.HTTPError:
            logger.exception("Dooray 알림 발송 실패")
            return False

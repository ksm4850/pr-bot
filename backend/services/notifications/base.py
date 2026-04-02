from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class NotificationMessage:
    """알림 메시지"""
    bot_name: str = ""
    bot_icon_image: str = "https://i.postimg.cc/QC0xBch6/Dooray-Bot.png"
    text: str = ""
    title: str = ""
    title_link: str = ""
    attachment_text: str = ""
    color: str = "red"


class NotificationSender(ABC):
    """웹훅 알림 발송 추상 클래스"""

    @property
    @abstractmethod
    def name(self) -> str:
        """알림 서비스 이름 (dooray, slack 등)"""
        pass

    @abstractmethod
    async def send(self, message: NotificationMessage) -> bool:
        """
        알림 발송

        Returns:
            bool: 발송 성공 여부
        """
        pass

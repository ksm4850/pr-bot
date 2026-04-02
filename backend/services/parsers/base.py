import json
from abc import ABC, abstractmethod

from app.models.error import ParsedError
from app.models.job import ErrorSource


class ErrorParser(ABC):
    """에러 파서 추상 클래스"""

    @property
    @abstractmethod
    def source(self) -> ErrorSource:
        """에러 소스 타입"""
        pass

    @abstractmethod
    def parse(self, payload: dict) -> ParsedError:
        """
        webhook payload → ParsedError 변환

        Args:
            payload: 원본 webhook payload (dict)

        Returns:
            ParsedError: 파싱된 에러 정보
        """
        pass

    def _attach_raw_payload(self, parsed: ParsedError, payload: dict) -> ParsedError:
        """원본 payload 첨부"""
        parsed.raw_payload = json.dumps(payload, ensure_ascii=False)
        return parsed

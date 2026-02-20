import pytest

from app.models.job import ErrorSource
from app.services.parsers import get_parser
from app.services.parsers.sentry import SentryParser


class TestSentryParser:
    """Sentry 파서 테스트"""

    def test_source_is_sentry(self):
        """파서 소스가 SENTRY인지 확인"""
        parser = SentryParser()
        assert parser.source == ErrorSource.SENTRY

    def test_parse_full_payload(self, sentry_payload):
        """전체 payload 파싱"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        assert parsed.source == ErrorSource.SENTRY
        assert parsed.source_issue_id == "7241469116"
        assert parsed.title == "ZeroDivisionError: division by zero"
        assert parsed.message == "division by zero"
        assert parsed.level == "error"
        assert parsed.environment == "prod"
        assert parsed.exception_type == "ZeroDivisionError"
        assert parsed.transaction == "/api/test"

    def test_parse_extracts_last_in_app_frame(self, sentry_payload):
        """마지막 in_app=True 프레임이 에러 위치로 추출되는지 확인"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        # 마지막 in_app frame: app/main.py:42 trigger_error
        assert parsed.filename == "app/main.py"
        assert parsed.lineno == 42
        assert parsed.function == "trigger_error"

    def test_parse_filters_in_app_frames_only(self, sentry_payload):
        """in_app=True 프레임만 파싱되는지 확인"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        # in_app=True인 프레임만 (라이브러리 코드 제외)
        assert len(parsed.frames) == 2
        assert parsed.frames[0].filename == "app/utils.py"
        assert parsed.frames[0].lineno == 50
        assert parsed.frames[1].filename == "app/main.py"

    def test_parse_frame_context(self, sentry_payload):
        """프레임의 context 정보가 파싱되는지 확인"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        first_frame = parsed.frames[0]
        assert first_frame.context_line == "    result = process(data)"
        assert first_frame.pre_context == ["def helper():", "    data = get_data()"]
        assert first_frame.post_context == ["    return result", ""]

    def test_parse_source_url(self, sentry_payload):
        """소스 URL이 파싱되는지 확인"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        assert parsed.source_url == "https://sentry.io/organizations/test/issues/7241469116/"

    def test_parse_attaches_raw_payload(self, sentry_payload):
        """원본 payload가 첨부되는지 확인"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload)

        assert parsed.raw_payload is not None
        assert "7241469116" in parsed.raw_payload

    def test_parse_minimal_payload(self, sentry_payload_minimal):
        """최소 payload 파싱 (stacktrace 없음)"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload_minimal)

        assert parsed.source_issue_id == "abc123"
        assert parsed.title == "Minimal error"
        assert parsed.level == "warning"
        assert parsed.filename is None
        assert parsed.lineno is None
        assert len(parsed.frames) == 0

    def test_parse_fallback_to_event_id(self, sentry_payload_minimal):
        """issue_id 없을 때 event_id로 fallback"""
        parser = SentryParser()
        parsed = parser.parse(sentry_payload_minimal)

        assert parsed.source_issue_id == "abc123"


class TestParserRegistry:
    """파서 레지스트리 테스트"""

    def test_get_sentry_parser(self):
        """Sentry 파서 가져오기"""
        parser = get_parser(ErrorSource.SENTRY)
        assert isinstance(parser, SentryParser)

    def test_get_unknown_parser_raises(self):
        """미등록 소스 요청 시 에러"""
        with pytest.raises(ValueError, match="Unknown error source"):
            get_parser(ErrorSource.CLOUDWATCH)

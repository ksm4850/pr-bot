from pydantic import BaseModel

from app.models.error import ParsedError, StackFrame
from app.models.job import ErrorSource
from app.services.parsers.base import ErrorParser


# Sentry 전용 Pydantic 모델 (파싱용)
class SentryStacktraceFrame(BaseModel):
    filename: str | None = None
    abs_path: str | None = None
    function: str | None = None
    lineno: int | None = None
    colno: int | None = None
    context_line: str | None = None
    pre_context: list[str] | None = None
    post_context: list[str] | None = None
    in_app: bool | None = None  # 사용자 코드 여부

    model_config = {"extra": "ignore"}


class SentryStacktrace(BaseModel):
    frames: list[SentryStacktraceFrame] = []

    model_config = {"extra": "ignore"}


class SentryExceptionValue(BaseModel):
    """exception.values[] 항목"""
    type: str | None = None  # ZeroDivisionError
    value: str | None = None  # division by zero
    stacktrace: SentryStacktrace | None = None

    model_config = {"extra": "ignore"}


class SentryException(BaseModel):
    """exception 필드"""
    values: list[SentryExceptionValue] = []

    model_config = {"extra": "ignore"}


class SentryOccurrence(BaseModel):
    """performance issue 등 occurrence 기반 이벤트"""
    issueTitle: str | None = None       # "N+1 Query"
    subtitle: str | None = None         # 실제 쿼리/설명
    culprit: str | None = None
    evidenceDisplay: list[dict] | None = None

    model_config = {"extra": "ignore"}


class SentryEvent(BaseModel):
    event_id: str | None = None
    project: int | str | None = None  # Sentry project ID (projects 테이블 조회용)
    issue_id: str | None = None
    title: str | None = None
    message: str | None = None
    platform: str | None = None
    level: str | None = None
    culprit: str | None = None
    environment: str | None = None
    transaction: str | None = None
    web_url: str | None = None
    exception: SentryException | None = None
    occurrence: SentryOccurrence | None = None

    model_config = {"extra": "ignore"}


class SentryWebhookData(BaseModel):
    event: SentryEvent
    triggered_rule: str | None = None

    model_config = {"extra": "ignore"}


class SentryWebhookPayload(BaseModel):
    action: str
    data: SentryWebhookData

    model_config = {"extra": "ignore"}


class SentryParser(ErrorParser):
    """Sentry webhook 파서"""

    @property
    def source(self) -> ErrorSource:
        return ErrorSource.SENTRY

    def parse(self, payload: dict) -> ParsedError:
        webhook = SentryWebhookPayload.model_validate(payload)
        event = webhook.data.event

        # exception.values[-1]에서 실제 예외 정보 추출
        exception_type: str | None = None
        exception_message: str | None = None
        all_frames: list[SentryStacktraceFrame] = []

        if event.exception and event.exception.values:
            # 마지막 exception이 실제 에러 (ExceptionGroup 등 제외)
            last_exc = event.exception.values[-1]
            exception_type = last_exc.type
            exception_message = last_exc.value

            if last_exc.stacktrace:
                all_frames = last_exc.stacktrace.frames

        # in_app=True 프레임만 필터링 (사용자 코드만)
        in_app_frames: list[StackFrame] = []
        for f in all_frames:
            if f.in_app:
                in_app_frames.append(
                    StackFrame(
                        filename=f.filename,
                        abs_path=f.abs_path,
                        function=f.function,
                        lineno=f.lineno,
                        colno=f.colno,
                        context_line=f.context_line,
                        pre_context=f.pre_context,
                        post_context=f.post_context,
                    )
                )

        # 마지막 in_app 프레임이 에러 발생 위치
        last_frame = in_app_frames[-1] if in_app_frames else None

        # occurrence 기반 이슈 (N+1 Query, Slow DB Query 등)
        occ = event.occurrence
        issue_title: str | None = None
        subtitle: str | None = None
        if occ:
            issue_title = occ.issueTitle
            subtitle = occ.subtitle

        # title: occurrence.issueTitle > event.title > exception 조합
        title = issue_title or event.title
        if not title and exception_type:
            title = f"{exception_type}: {exception_message}" if exception_message else exception_type

        # message: exception_message가 없으면 subtitle 사용
        message = exception_message or subtitle

        parsed = ParsedError(
            source=self.source,
            source_project_id=str(event.project) if event.project else None,
            source_issue_id=event.issue_id or event.event_id or "unknown",
            title=title or "Unknown Error",
            subtitle=subtitle,
            message=message,
            level=event.level,
            environment=event.environment,
            filename=last_frame.filename if last_frame else None,
            lineno=last_frame.lineno if last_frame else None,
            function=last_frame.function if last_frame else None,
            frames=in_app_frames,
            source_url=event.web_url,
            exception_type=exception_type,
            transaction=event.transaction,
        )

        return self._attach_raw_payload(parsed, payload)

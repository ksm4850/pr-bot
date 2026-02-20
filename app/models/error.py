from pydantic import BaseModel

from app.models.job import ErrorSource


class StackFrame(BaseModel):
    """스택트레이스 프레임 (공통)"""

    filename: str | None = None
    abs_path: str | None = None
    function: str | None = None
    lineno: int | None = None
    colno: int | None = None
    context_line: str | None = None
    pre_context: list[str] | None = None
    post_context: list[str] | None = None


class ParsedError(BaseModel):
    """파싱된 에러 정보 (모든 소스 공통)"""

    # 소스 정보
    source: ErrorSource
    source_project_id: str | None = None  # projects 테이블 조회용
    source_issue_id: str  # 소스별 고유 ID

    # 에러 정보
    title: str
    message: str | None = None  # exception message
    level: str | None = None
    environment: str | None = None  # dev, prod 등 → 깃 브랜치 결정

    # 예외 타입
    exception_type: str | None = None  # ZeroDivisionError, ValueError 등

    # API 엔드포인트
    transaction: str | None = None  # /api/users, /sentry-debug 등

    # 코드 위치 (에러 발생 지점, in_app=True 프레임 기준)
    filename: str | None = None
    lineno: int | None = None
    function: str | None = None

    # 스택트레이스 (in_app=True만)
    frames: list[StackFrame] = []

    # 원본 URL
    source_url: str | None = None

    # 원본 payload (JSON string)
    raw_payload: str | None = None

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class ErrorSource(str, Enum):
    SENTRY = "sentry"
    CLOUDWATCH = "cloudwatch"
    DATADOG = "datadog"


class JobTaskType(str, Enum):
    """에이전트 작업 이벤트 타입"""
    TOOL_USE = "tool_use"        # Claude가 도구 호출
    MESSAGE = "message"          # Claude 텍스트 응답
    ERROR = "error"              # 에러 발생
    STATUS = "status"            # 상태 변경 (processing → done 등)


# SQLAlchemy Base
class Base(DeclarativeBase):
    pass


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.PENDING.value)

    # 에러 소스
    source: Mapped[str] = mapped_column(String(50))
    source_project_id: Mapped[str | None] = mapped_column(String(255), nullable=True)  # projects 테이블 조회용
    source_issue_id: Mapped[str] = mapped_column(String(255))

    # 에러 정보
    title: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    exception_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 코드 위치
    filename: Mapped[str | None] = mapped_column(Text, nullable=True)
    lineno: Mapped[int | None] = mapped_column(Integer, nullable=True)
    function: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stacktrace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 작업 결과
    work_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 에이전트 작업 브랜치
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 메타
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("idx_jobs_status", "status"),
        UniqueConstraint("source", "source_issue_id", name="uq_jobs_source_issue"),
    )


class JobTaskModel(Base):
    """Job 에이전트 작업 히스토리

    Job 하나에 대한 Claude Agent의 작업 내역을 순서대로 기록.
    재시도 시에도 누적 저장하여 전체 추적 가능.
    """

    __tablename__ = "job_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)       # job 내 순서
    type: Mapped[str] = mapped_column(String(20), nullable=False)        # JobTaskType
    content: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON: 도구명/입력/출력/메시지 등
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))

    __table_args__ = (
        Index("idx_job_tasks_job_id", "job_id"),
    )


# ── Pydantic Models ──────────────────────────────────────────────

class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.PENDING
    source: ErrorSource
    source_project_id: str | None = None
    source_issue_id: str
    title: str
    message: str | None = None
    level: str | None = None
    environment: str | None = None
    exception_type: str | None = None
    transaction: str | None = None
    filename: str | None = None
    lineno: int | None = None
    function: str | None = None
    stacktrace: str | None = None
    work_branch: str | None = None
    error_log: str | None = None
    retry_count: int = 0
    source_url: str | None = None
    raw_payload: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_orm(cls, db: JobModel) -> "Job":
        return cls(
            id=db.id,
            status=JobStatus(db.status),
            source=ErrorSource(db.source),
            source_project_id=db.source_project_id,
            source_issue_id=db.source_issue_id,
            title=db.title,
            message=db.message,
            level=db.level,
            environment=db.environment,
            exception_type=db.exception_type,
            transaction=db.transaction,
            filename=db.filename,
            lineno=db.lineno,
            function=db.function,
            stacktrace=db.stacktrace,
            work_branch=db.work_branch,
            error_log=db.error_log,
            retry_count=db.retry_count,
            source_url=db.source_url,
            raw_payload=db.raw_payload,
            created_at=db.created_at,
            updated_at=db.updated_at,
        )


class JobTask(BaseModel):
    id: str
    job_id: str
    sequence: int
    type: JobTaskType
    content: str | None = None  # JSON string
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_orm(cls, db: JobTaskModel) -> "JobTask":
        return cls(
            id=db.id,
            job_id=db.job_id,
            sequence=db.sequence,
            type=JobTaskType(db.type),
            content=db.content,
            created_at=db.created_at,
        )

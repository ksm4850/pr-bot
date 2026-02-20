from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.job import Base


class RepoPlatform(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


class ProjectModel(Base):
    """프로젝트-레포 매핑 테이블

    에러 소스의 project_id → git repo URL 매핑
    예: sentry + "4509981525278720" → https://github.com/org/repo

    브랜치는 저장하지 않음. 웹훅의 environment 값으로 런타임에 결정.
    (dev → develop, prod → main 등은 Agent가 판단)
    """

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # 에러 소스 식별 (sentry, cloudwatch, datadog 등)
    source: Mapped[str] = mapped_column(String(50))         # "sentry"
    source_project_id: Mapped[str] = mapped_column(Text)   # "4509981525278720"

    # Git 레포 정보
    repo_url: Mapped[str] = mapped_column(Text)            # "https://github.com/org/repo"
    repo_platform: Mapped[str] = mapped_column(String(20)) # "github" | "gitlab"

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint(
            "source", "source_project_id",
            name="uq_projects_source_project"
        ),
    )


class Project(BaseModel):
    """Project Pydantic 모델"""

    id: str
    source: str
    source_project_id: str
    repo_url: str
    repo_platform: RepoPlatform
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_orm(cls, db_model: ProjectModel) -> "Project":
        return cls(
            id=db_model.id,
            source=db_model.source,
            source_project_id=db_model.source_project_id,
            repo_url=db_model.repo_url,
            repo_platform=RepoPlatform(db_model.repo_platform),
            created_at=db_model.created_at,
            updated_at=db_model.updated_at,
        )
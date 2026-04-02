from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from models.job import Base


class SettingModel(Base):
    """앱 설정 key-value 테이블"""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )


class Setting(BaseModel):
    """Setting Pydantic 모델"""

    key: str
    value: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_orm(cls, db_model: SettingModel) -> "Setting":
        return cls(
            key=db_model.key,
            value=db_model.value,
            updated_at=db_model.updated_at,
        )
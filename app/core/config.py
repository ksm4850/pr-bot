from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_path: Path = Path("data/jobs.db")

    # Worker
    worker_poll_interval: int = 5  # seconds

    # Workspace
    workspace_dir: Path = Path.home() / ".pr-bot-workspaces"

    @field_validator("workspace_dir", mode="before")
    @classmethod
    def _default_workspace(cls, v: str | Path | None) -> Path:
        if not v:
            return Path.home() / ".pr-bot-workspaces"
        return Path(v)

    # API Keys (optional for now)
    anthropic_api_key: str | None = None
    github_token: str | None = None
    gitlab_token: str | None = None

    # Sentry
    sentry_webhook_secret: str | None = None
    sentry_dsn: str | None = None


settings = Settings()

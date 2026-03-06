from pathlib import Path
from typing import Literal

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

    # Agent mode: "api" = Anthropic API 직접 호출, "claude-code" = claude CLI subprocess
    agent_mode: Literal["api", "claude-code"] = "api"

    # Bot git identity
    bot_git_name: str = "pr-bot"
    bot_git_email: str = "pr-bot@noreply"

    # API Keys (optional for now)
    anthropic_api_key: str | None = None
    github_token: str | None = None
    gitlab_token: str | None = None

    # Claude Code 구독 계정 토큰 (쉼표 구분)
    # setup-token으로 발급받은 long-lived token 목록
    claude_tokens: list[str] = []

    @field_validator("claude_tokens", mode="before")
    @classmethod
    def _parse_claude_tokens(cls, v: str | list | None) -> list[str]:
        if not v:
            return []
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v

    # Sentry
    sentry_webhook_secret: str | None = None
    sentry_dsn: str | None = None


settings = Settings()
